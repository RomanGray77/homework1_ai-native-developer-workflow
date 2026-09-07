from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .decorators import FAMILY_MEMBER_SESSION_KEY, admin_required
from .forms import CreateChoreForm, EditChoreForm
from .models import Chore, FamilyMember

# The personal chore view (#11) now exists, so a successful selection lands
# there instead of on the "health" placeholder used before #11 shipped.
POST_SELECT_REDIRECT_URL_NAME = "personal_chores"

# Same forward-reference pattern as POST_SELECT_REDIRECT_URL_NAME above:
# the family overview (#12) is where a successfully created chore should
# send the admin, but #12 does not exist yet. Points at "health" as a
# placeholder so this doesn't 500/NoReverseMatch in the meantime; update
# this single constant once #12 lands.
POST_CREATE_REDIRECT_URL_NAME = "health"

# Same forward-reference pattern as POST_CREATE_REDIRECT_URL_NAME above:
# points at "health" as a placeholder until #12 lands. Update this single
# constant once it exists.
POST_EDIT_REDIRECT_URL_NAME = "health"

# The personal chore view (#11) now exists, so deactivating a chore redirects
# there instead of the "health" placeholder used before #11 shipped.
POST_DEACTIVATE_REDIRECT_URL_NAME = "personal_chores"


def health(request):
    return HttpResponse("ok")


def select_member(request):
    """Let a user declare which FamilyMember they are for this session.

    No password, no Django auth login - just a session flag (#7). Always
    reachable, even when a member is already selected, so someone can
    switch identity without a logout step.
    """
    members = FamilyMember.objects.order_by("name")

    if request.method == "POST":
        raw_member_id = request.POST.get("family_member_id")

        member = None
        if raw_member_id is not None:
            try:
                member = FamilyMember.objects.filter(pk=raw_member_id).first()
            except (ValueError, TypeError):
                # Tampered/malformed value (e.g. non-numeric) - handled the
                # same as "no such member" below, never a crash.
                member = None

        if member is None:
            return render(
                request,
                "chores/select_member.html",
                {
                    "members": members,
                    "error": "That's not a valid family member. Please pick again.",
                },
            )

        request.session[FAMILY_MEMBER_SESSION_KEY] = member.pk
        return redirect(POST_SELECT_REDIRECT_URL_NAME)

    return render(request, "chores/select_member.html", {"members": members})


@admin_required
def create_chore(request):
    """Let an admin create a one-time or recurring chore (#8).

    Gated by admin_required (#6): no session -> redirect to select_member,
    non-admin session -> 403. On a valid POST the Chore is created (with
    is_active=True by the model default and no CompletionRecord) and the
    response redirects to POST_CREATE_REDIRECT_URL_NAME. An invalid POST
    re-renders the same template with the bound form and its errors.
    """
    if request.method == "POST":
        form = CreateChoreForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect(POST_CREATE_REDIRECT_URL_NAME)
    else:
        form = CreateChoreForm()

    return render(request, "chores/create_chore.html", {"form": form})


@admin_required
def edit_chore(request, pk):
    """Let an admin edit an existing chore's editable fields (#9).

    Gated by admin_required (#6), same as create_chore. The chore's
    chore_type is fixed at creation time (#8) and is never read from
    submitted data - EditChoreForm has no chore_type field at all, and its
    clean() enforces the due_date/recurrence mutual-exclusivity rule using
    this chore's existing chore_type. A nonexistent pk is a 404 via
    get_object_or_404, for both GET and POST. Editing never touches
    CompletionRecord rows - only the Chore's own fields are updated.
    """
    chore = get_object_or_404(Chore, pk=pk)

    if request.method == "POST":
        form = EditChoreForm(request.POST, chore=chore)
        if form.is_valid():
            form.save()
            return redirect(POST_EDIT_REDIRECT_URL_NAME)
    else:
        form = EditChoreForm(
            chore=chore,
            initial={
                "title": chore.title,
                "owner": chore.owner_id,
                "priority": chore.priority,
                "due_date": chore.due_date,
                "recurrence": chore.recurrence,
            },
        )

    return render(request, "chores/edit_chore.html", {"form": form, "chore": chore})


@admin_required
@require_POST
def deactivate_chore(request, pk):
    """Let an admin deactivate (soft-delete) a chore (#10).

    Gated by admin_required (#6), same as create_chore/edit_chore, and
    POST-only: require_POST turns a GET into a 405 before admin_required's
    session/role checks even matter for method, but admin_required still
    runs first so a missing/non-admin session gets its usual redirect/403
    treatment rather than a 405. The chore row is never deleted - only
    is_active flips to False - so existing CompletionRecord history is left
    completely untouched. A nonexistent pk is a 404 via get_object_or_404.
    Deactivating an already-inactive chore is a no-op (no write, no error):
    it still redirects like a normal success. There is no reactivate/undo
    action - deliberately out of scope per plan.md's Final MVP Boundary.
    """
    chore = get_object_or_404(Chore, pk=pk)

    if chore.is_active:
        chore.is_active = False
        chore.save(update_fields=["is_active"])

    return redirect(POST_DEACTIVATE_REDIRECT_URL_NAME)


def personal_chores(request):
    """Show the selected family member their own open chores (#11).

    No admin_required gate - any selected family member (admin or not) may
    view their own chores. The session check mirrors admin_required's
    pattern (chores/decorators.py): missing, malformed (non-numeric), or
    stale (no matching FamilyMember) session values are all treated the same
    - redirect to select_member, never a 500.

    "Open" = Chore.objects.active() (#10, the is_active=True half, built on
    top of that queryset method rather than re-derived) AND no
    CompletionRecord yet. Results are grouped into four buckets compared
    against today's date - Overdue, Today, Upcoming, and Later/No due date
    (which also permanently holds every recurring chore, since due_date
    never applies to chore_type=recurring) - each ordered by due_date
    ascending (nulls last within Later/No due date, which is all nulls
    anyway) then by title for a deterministic, testable order.
    """
    member_id = request.session.get(FAMILY_MEMBER_SESSION_KEY)

    member = None
    if member_id is not None:
        try:
            member = FamilyMember.objects.filter(pk=member_id).first()
        except (ValueError, TypeError):
            # Malformed session value (e.g. non-numeric) - treat as "no
            # selection" rather than letting the lookup error out.
            member = None

    if member is None:
        return redirect("select_member")

    open_chores = (
        Chore.objects.active()
        .filter(owner=member)
        .exclude(completion_records__isnull=False)
        .order_by("title")
    )

    today = timezone.localdate()

    overdue = []
    due_today = []
    upcoming = []
    later_or_no_due_date = []

    for chore in open_chores:
        if chore.due_date is None:
            later_or_no_due_date.append(chore)
        elif chore.due_date < today:
            overdue.append(chore)
        elif chore.due_date == today:
            due_today.append(chore)
        else:
            upcoming.append(chore)

    # Chores with a due_date are already ordered by title (the queryset's
    # order_by above); sort each dated bucket by due_date ascending while
    # keeping title as the tiebreaker via a stable sort.
    overdue.sort(key=lambda chore: chore.due_date)
    due_today.sort(key=lambda chore: chore.due_date)
    upcoming.sort(key=lambda chore: chore.due_date)

    return render(
        request,
        "chores/personal_chores.html",
        {
            "member": member,
            "overdue": overdue,
            "due_today": due_today,
            "upcoming": upcoming,
            "later_or_no_due_date": later_or_no_due_date,
            "has_open_chores": bool(
                overdue or due_today or upcoming or later_or_no_due_date
            ),
        },
    )
