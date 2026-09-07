from django.http import HttpResponse
from django.shortcuts import redirect, render

from .decorators import FAMILY_MEMBER_SESSION_KEY
from .models import FamilyMember

# The personal chore view (#11) is what a selection should redirect to, but
# #11 has not been implemented yet. Redirecting to a URL name that does not
# exist would turn every successful selection into a 500/NoReverseMatch, so
# this points at "health" as a placeholder in the meantime. Update this once
# #11 lands (see the issue #7 comment for the same note).
POST_SELECT_REDIRECT_URL_NAME = "health"


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
