from functools import wraps

from django.http import HttpResponseForbidden
from django.shortcuts import redirect

from .models import FamilyMember

# Session key contract shared with the family-member selection screen (#7).
FAMILY_MEMBER_SESSION_KEY = "family_member_id"

# URL name of the family-member selection screen (#7). Hard-coded here per
# #6's constraints so #7 can register a URL with this exact name; until #7
# lands, reverse()/redirect() for this name will not resolve.
SELECT_MEMBER_URL_NAME = "select_member"


def admin_required(view_func):
    """View decorator requiring the session's family member to be an admin.

    - No `family_member_id` in the session -> redirect to the family member
      selection screen.
    - `family_member_id` present but malformed or matching no `FamilyMember`
      row -> treated the same as "no selection": redirect, never a 500.
    - Selected `FamilyMember` exists but `is_admin` is False -> 403 Forbidden.
    - Selected `FamilyMember` exists and is an admin -> the view runs.
    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        member_id = request.session.get(FAMILY_MEMBER_SESSION_KEY)

        member = None
        if member_id is not None:
            try:
                member = FamilyMember.objects.filter(pk=member_id).first()
            except (ValueError, TypeError):
                # Malformed session value (e.g. non-numeric) - treat as
                # "no selection" rather than letting the lookup error out.
                member = None

        if member is None:
            return redirect(SELECT_MEMBER_URL_NAME)

        if not member.is_admin:
            return HttpResponseForbidden()

        return view_func(request, *args, **kwargs)

    return _wrapped_view
