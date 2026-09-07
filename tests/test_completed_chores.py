"""Tests for chores.views.completed_chores (#14).

No session gate at all - same pattern as family_overview (#12): the view
must render identically whether family_member_id is absent, malformed,
stale, or a valid selection (admin or not). Every CompletionRecord field
shown (chore title, chore's current owner, completed_by, completed_at) is
direct FK access - no schema or extra-query changes. Ordered by
completed_at descending with a pk-descending tiebreak. Read-only: no
edit/delete controls. Also confirms none of the existing
POST_*_REDIRECT_URL_NAME constants were repointed here.
"""

import datetime

import pytest
from django.urls import reverse

from chores.models import Chore, CompletionRecord, FamilyMember


def _log_in_as(client, member):
    session = client.session
    session["family_member_id"] = member.pk
    session.save()


def _make_chore(owner, **kwargs):
    kwargs.setdefault("title", "Dishes")
    kwargs.setdefault("chore_type", Chore.ChoreType.ONE_TIME)
    return Chore.objects.create(owner=owner, **kwargs)


@pytest.mark.django_db
def test_completed_chores_url_name_resolves():
    assert reverse("completed_chores") == "/chores/completed/"


@pytest.mark.django_db
def test_completion_appears_with_correct_fields(client):
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    completer = FamilyMember.objects.create(name="Eli", is_admin=False)
    chore = _make_chore(owner, title="Dishes")
    record = CompletionRecord.objects.create(
        chore=chore,
        completed_by=completer,
        completed_at=datetime.datetime(2026, 9, 1, 12, 0, tzinfo=datetime.timezone.utc),
    )

    response = client.get(reverse("completed_chores"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Dishes" in content
    assert "Dana" in content
    assert "Eli" in content
    assert str(record.completed_at.year) in content


@pytest.mark.django_db
def test_current_owner_shown_not_owner_at_completion_time(client):
    original_owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    new_owner = FamilyMember.objects.create(name="Frank", is_admin=False)
    chore = _make_chore(original_owner, title="Dishes")
    CompletionRecord.objects.create(chore=chore, completed_by=original_owner)

    chore.owner = new_owner
    chore.save(update_fields=["owner"])

    response = client.get(reverse("completed_chores"))
    content = response.content.decode()

    assert "Frank" in content
    # The old owner's name should not appear anywhere near the owner label
    # (original_owner also appears as completed_by, so just check the
    # current owner is what's rendered as owner).
    assert response.context["records"][0].chore.owner == new_owner


@pytest.mark.django_db
def test_ordering_most_recent_first_with_tiebreak(client):
    member = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = _make_chore(member, title="Dishes")
    same_time = datetime.datetime(2026, 9, 1, 12, 0, tzinfo=datetime.timezone.utc)

    older = CompletionRecord.objects.create(
        chore=chore,
        completed_by=member,
        completed_at=datetime.datetime(2026, 8, 1, 12, 0, tzinfo=datetime.timezone.utc),
    )
    tie_1 = CompletionRecord.objects.create(
        chore=chore, completed_by=member, completed_at=same_time
    )
    tie_2 = CompletionRecord.objects.create(
        chore=chore, completed_by=member, completed_at=same_time
    )
    newest = CompletionRecord.objects.create(
        chore=chore,
        completed_by=member,
        completed_at=datetime.datetime(2026, 9, 5, 12, 0, tzinfo=datetime.timezone.utc),
    )

    response = client.get(reverse("completed_chores"))
    records = list(response.context["records"])

    # newest first, then the tied pair ordered by pk descending, then oldest
    expected_tie_order = sorted([tie_1, tie_2], key=lambda r: -r.pk)
    assert records == [newest, *expected_tie_order, older]


@pytest.mark.django_db
def test_empty_state_when_no_completions(client):
    response = client.get(reverse("completed_chores"))

    assert response.status_code == 200
    assert "no chores have been completed" in response.content.decode().lower()


@pytest.mark.django_db
def test_no_session_at_all_still_renders(client):
    member = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = _make_chore(member, title="Dishes")
    CompletionRecord.objects.create(chore=chore, completed_by=member)

    response = client.get(reverse("completed_chores"))

    assert response.status_code == 200
    assert "Dishes" in response.content.decode()


@pytest.mark.django_db
def test_malformed_session_value_still_renders(client):
    member = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = _make_chore(member, title="Dishes")
    CompletionRecord.objects.create(chore=chore, completed_by=member)
    session = client.session
    session["family_member_id"] = "not-an-int"
    session.save()

    response = client.get(reverse("completed_chores"))

    assert response.status_code == 200
    assert "Dishes" in response.content.decode()


@pytest.mark.django_db
def test_stale_nonexistent_session_id_still_renders(client):
    member = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = _make_chore(member, title="Dishes")
    CompletionRecord.objects.create(chore=chore, completed_by=member)
    session = client.session
    session["family_member_id"] = 999999
    session.save()

    response = client.get(reverse("completed_chores"))

    assert response.status_code == 200
    assert "Dishes" in response.content.decode()


@pytest.mark.django_db
def test_non_admin_selected_member_can_access(client):
    member = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = _make_chore(member, title="Dishes")
    CompletionRecord.objects.create(chore=chore, completed_by=member)
    _log_in_as(client, member)

    response = client.get(reverse("completed_chores"))

    assert response.status_code == 200
    assert "Dishes" in response.content.decode()


@pytest.mark.django_db
def test_admin_selected_member_can_access(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    chore = _make_chore(admin, title="Dishes")
    CompletionRecord.objects.create(chore=chore, completed_by=admin)
    _log_in_as(client, admin)

    response = client.get(reverse("completed_chores"))

    assert response.status_code == 200
    assert "Dishes" in response.content.decode()


@pytest.mark.django_db
def test_no_edit_or_delete_controls_in_template(client):
    member = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = _make_chore(member, title="Dishes")
    CompletionRecord.objects.create(chore=chore, completed_by=member)

    response = client.get(reverse("completed_chores"))
    content = response.content.decode().lower()

    assert "<form" not in content
    assert "edit" not in content
    assert "delete" not in content


@pytest.mark.django_db
def test_post_redirect_constants_unchanged():
    # Confirms #14 did not touch any existing POST_*_REDIRECT_URL_NAME
    # constant - completed_chores is not a redirect target for anything.
    from chores import views

    assert views.POST_SELECT_REDIRECT_URL_NAME == "personal_chores"
    assert views.POST_CREATE_REDIRECT_URL_NAME == "family_overview"
    assert views.POST_EDIT_REDIRECT_URL_NAME == "family_overview"
    assert views.POST_DEACTIVATE_REDIRECT_URL_NAME == "personal_chores"
    assert views.POST_COMPLETE_REDIRECT_URL_NAME == "family_overview"
