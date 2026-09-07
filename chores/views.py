from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .decorators import FAMILY_MEMBER_SESSION_KEY, admin_required
from .forms import CreateChoreForm, EditChoreForm, EditCompletionRecordForm
from .models import Chore, CompletionRecord, FamilyMember

# The personal chore view (#11) now exists, so a successful selection lands
# there instead of on the "health" placeholder used before #11 shipped.
POST_SELECT_REDIRECT_URL_NAME = "personal_chores"

# The family overview (#12) now exists, so a successfully created chore
# lands there instead of the "health" placeholder used before #12 shipped.
POST_CREATE_REDIRECT_URL_NAME = "family_overview"

# Same forward-reference pattern as POST_CREATE_REDIRECT_URL_NAME above:
# the family overview (#12) now exists, so a successfully edited chore
# lands there instead of the "health" placeholder used before #12 shipped.
POST_EDIT_REDIRECT_URL_NAME = "family_overview"

# The personal chore view (#11) now exists, so deactivating a chore redirects
# there instead of the "health" placeholder used before #11 shipped.
POST_DEACTIVATE_REDIRECT_URL_NAME = "personal_chores"

# Same forward-reference pattern as the constants above. Targets
# family_overview specifically (not personal_chores): a non-owner who
# completes someone else's chore would never see that chore in their own
# personal view, so personal_chores would not visibly confirm anything (#13).
POST_COMPLETE_REDIRECT_URL_NAME = "family_overview"

# The completed_chores view (#14) is the natural home for both completion-
# record corrections below - it's the only place completed records are
# listed at all.
POST_EDIT_COMPLETION_REDIRECT_URL_NAME = "completed_chores"
POST_DELETE_COMPLETION_REDIRECT_URL_NAME = "completed_chores"


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


@require_POST
def complete_chore(request, pk):
    """Let any selected family member mark a chore as done (#13).

    No admin_required gate - unlike create_chore/edit_chore/deactivate_chore,
    completion is not admin-only: any valid selected member (admin or not)
    may complete any chore, not just their own. The session check mirrors
    personal_chores'/family_overview's inline pattern (not admin_required's,
    since there is no admin/role check here): missing, malformed, or stale
    family_member_id all redirect to select_member, never a 500. POST-only
    via require_POST, same as deactivate_chore (GET -> 405). A nonexistent
    pk is a 404 via get_object_or_404.

    On success, records a CompletionRecord(chore=chore, completed_by=<the
    selected member>, completed_at=timezone.now()) unless one already exists
    for this chore - completing an already-completed chore (or a
    double-submit race) is a no-op: no second record, no error, same
    redirect as success. Mirrors deactivate_chore's "already inactive is a
    no-op" behavior. Redirects to POST_COMPLETE_REDIRECT_URL_NAME
    (family_overview, not personal_chores) since a non-owner completing
    someone else's chore would never see it in their own personal view.

    If this first (non-idempotent) completion is for a chore_type=recurring
    chore, it also generates the next open occurrence (#15) via
    _generate_next_occurrence - a brand-new Chore row, cloned from this one,
    with no CompletionRecord of its own. The completed row and its
    CompletionRecord are never mutated for this. One-time chores are
    unaffected, and the idempotent no-op path below never triggers
    generation, so re-POSTing against an already-completed recurring chore
    creates no additional rows.
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

    chore = get_object_or_404(Chore, pk=pk)

    if not CompletionRecord.objects.filter(chore=chore).exists():
        CompletionRecord.objects.create(
            chore=chore, completed_by=member, completed_at=timezone.now()
        )

        if chore.chore_type == Chore.ChoreType.RECURRING:
            _generate_next_occurrence(chore)

    return redirect(POST_COMPLETE_REDIRECT_URL_NAME)


def _generate_next_occurrence(chore):
    """Create the next open occurrence of a just-completed recurring chore (#15).

    Clones title/owner/priority/chore_type/recurrence onto a brand-new Chore
    row with is_active=True and no CompletionRecord, leaving the completed
    `chore` row (and its CompletionRecord history) completely untouched.
    due_date is deliberately not copied/computed - it stays one-time-only
    per _docs/architecture.md; `recurrence` alone documents cadence for the
    MVP. Only called from complete_chore's first-completion branch, so it
    never runs on the idempotent re-completion no-op.
    """
    return Chore.objects.create(
        title=chore.title,
        owner=chore.owner,
        priority=chore.priority,
        chore_type=chore.chore_type,
        recurrence=chore.recurrence,
        is_active=True,
    )


def _group_chores_by_due_date(chores):
    """Group an iterable of open chores into the four #11/#12 buckets.

    Shared by personal_chores (#11) and family_overview (#12) so the
    grouping behavior stays identical between the two views (extraction is
    optional per #12's constraints, but kept here since the logic is
    otherwise a verbatim duplicate). `chores` must already be ordered by
    title so buckets come out with title as a stable tiebreaker; each dated
    bucket is then sorted by due_date ascending on top of that.
    """
    today = timezone.localdate()

    overdue = []
    due_today = []
    upcoming = []
    later_or_no_due_date = []

    for chore in chores:
        if chore.due_date is None:
            later_or_no_due_date.append(chore)
        elif chore.due_date < today:
            overdue.append(chore)
        elif chore.due_date == today:
            due_today.append(chore)
        else:
            upcoming.append(chore)

    overdue.sort(key=lambda chore: chore.due_date)
    due_today.sort(key=lambda chore: chore.due_date)
    upcoming.sort(key=lambda chore: chore.due_date)

    return overdue, due_today, upcoming, later_or_no_due_date


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

    overdue, due_today, upcoming, later_or_no_due_date = _group_chores_by_due_date(
        open_chores
    )

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


def family_overview(request):
    """Show every open chore across the whole household (#12).

    No session gate at all - unlike personal_chores (#11), this view is not
    personalized to any one member, so it renders identically whether
    `family_member_id` is absent, malformed, stale, or a valid selection
    (admin or not). It never redirects to select_member and never checks
    is_admin (plan.md story 8: "All family members can access the family
    overview").

    "Open" = Chore.objects.active() (#10, the is_active=True half, built on
    top of that queryset method rather than re-derived) AND no
    CompletionRecord yet - same definition as #11, but across every owner
    rather than scoped to a session selection. Results are grouped into the
    same four due_date buckets as #11 via the shared
    _group_chores_by_due_date helper, each ordered by due_date ascending
    (nulls last within Later/No due date) then by title.
    """
    open_chores = (
        Chore.objects.active()
        .exclude(completion_records__isnull=False)
        .select_related("owner")
        .order_by("title")
    )

    overdue, due_today, upcoming, later_or_no_due_date = _group_chores_by_due_date(
        open_chores
    )

    return render(
        request,
        "chores/family_overview.html",
        {
            "overdue": overdue,
            "due_today": due_today,
            "upcoming": upcoming,
            "later_or_no_due_date": later_or_no_due_date,
            "has_open_chores": bool(
                overdue or due_today or upcoming or later_or_no_due_date
            ),
        },
    )


def completed_chores(request):
    """Show every completed chore, read-only (#14).

    No session gate at all - same pattern as family_overview (#12), not
    personal_chores'/select_member's redirect-if-no-session pattern: this
    view renders identically whether family_member_id is absent, malformed,
    stale, or a valid selection (admin or not). It never redirects to
    select_member and never checks is_admin. It is also not a redirect
    target for any POST action - the POST_*_REDIRECT_URL_NAME constants
    above are all untouched by this view.

    Every field shown (chore title, the chore's current owner, who
    completed it, when) is direct FK access on CompletionRecord - no schema
    or extra-query changes, per #14's acceptance criteria. "Current owner"
    is a live FK read (record.chore.owner), so a chore reassigned after
    completion shows its new owner here, not a point-in-time snapshot -
    that snapshot behavior is explicitly out of scope for #14.

    Ordered by completed_at descending (most recent first), with a
    secondary sort by pk descending so two records sharing the same
    completed_at still come out in a deterministic, testable order. This is
    read-only: no edit/delete controls in the template (corrections are
    #16).
    """
    records = CompletionRecord.objects.select_related(
        "chore", "chore__owner", "completed_by"
    ).order_by("-completed_at", "-pk")

    return render(
        request,
        "chores/completed_chores.html",
        {
            "records": records,
            "has_completed_chores": records.exists(),
        },
    )


@admin_required
def edit_completion_record(request, pk):
    """Let an admin correct a CompletionRecord's completed_by/completed_at (#16).

    Gated by admin_required (#6), same shape as edit_chore (#9): GET+POST,
    not POST-only. EditCompletionRecordForm has no `chore` field at all, so
    the record's `chore` FK is fixed and never reassigned here. A valid POST
    updates only `completed_by`/`completed_at` on this CompletionRecord and
    redirects to POST_EDIT_COMPLETION_REDIRECT_URL_NAME (completed_chores,
    #14). An invalid POST re-renders the same template with the bound form
    and its errors, same as edit_chore. This view never touches
    `Chore.is_active` or any other Chore field, and never calls
    _generate_next_occurrence (#15) directly - that helper is only ever
    invoked from complete_chore's first-completion branch, so nothing here
    can re-trigger it. A nonexistent pk is a 404 via get_object_or_404, for
    both GET and POST.
    """
    record = get_object_or_404(CompletionRecord, pk=pk)

    if request.method == "POST":
        form = EditCompletionRecordForm(request.POST, record=record)
        if form.is_valid():
            form.save()
            return redirect(POST_EDIT_COMPLETION_REDIRECT_URL_NAME)
    else:
        form = EditCompletionRecordForm(
            record=record,
            initial={
                "completed_by": record.completed_by_id,
                "completed_at": record.completed_at,
            },
        )

    return render(
        request,
        "chores/edit_completion_record.html",
        {"form": form, "record": record},
    )


@admin_required
@require_POST
def delete_completion_record(request, pk):
    """Let an admin delete a CompletionRecord outright (#16).

    Decorator order mirrors deactivate_chore (#10): admin_required runs
    first, so a missing/non-admin session gets its usual redirect/403
    treatment regardless of request method; require_POST then turns a GET
    from a valid admin session into a 405. A nonexistent pk is a 404 via
    get_object_or_404.

    Deleting the record is the whole implementation - no special-casing for
    one-time vs. recurring chores is needed. #11/#12 define "open" as
    active + no CompletionRecord, so once this row's only CompletionRecord
    is gone, that Chore (a one-time chore, or one occurrence row of a
    recurring chore) naturally reappears as open again. For a recurring
    chore, only this occurrence row's record is touched - the already
    -generated next occurrence (#15) and its own (still-absent)
    CompletionRecord are left alone, so both rows may be open at once.
    Redirects to POST_DELETE_COMPLETION_REDIRECT_URL_NAME (completed_chores,
    #14).
    """
    record = get_object_or_404(CompletionRecord, pk=pk)
    record.delete()
    return redirect(POST_DELETE_COMPLETION_REDIRECT_URL_NAME)
