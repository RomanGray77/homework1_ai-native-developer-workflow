"""Tests for chores.views.delete_completion_record (#16).

The view is gated by admin_required (#6) then require_POST, decorator order
mirroring deactivate_chore (#10): the access-control tests here mirror
tests/test_deactivate_chore.py's contract (no session -> redirect to
select_member, non-admin session -> 403 even for GET, admin GET -> 405)
against the real "delete_completion_record" URL. The rest covers: a valid
POST deletes the row and redirects to completed_chores (#14), deleting the
sole record for a one-time chore reopens it (reappears in personal_chores
and family_overview per #11/#12's shared "open" definition), deleting one
occurrence row's record in a recurring chore leaves the already-generated
next occurrence (#15) untouched (both open at once), and a nonexistent pk
is a 404.
"""

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
def test_no_session_redirects_to_select_member(client):
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = _make_chore(owner)
    record = CompletionRecord.objects.create(chore=chore, completed_by=owner)

    response = client.post(reverse("delete_completion_record", args=[record.pk]))

    assert response.status_code == 302
    assert response.url == reverse("select_member")
    assert CompletionRecord.objects.filter(pk=record.pk).exists()


@pytest.mark.django_db
def test_non_admin_gets_403(client):
    member = FamilyMember.objects.create(name="Bob", is_admin=False)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = _make_chore(owner)
    record = CompletionRecord.objects.create(chore=chore, completed_by=owner)
    _log_in_as(client, member)

    response = client.post(reverse("delete_completion_record", args=[record.pk]))

    assert response.status_code == 403
    assert CompletionRecord.objects.filter(pk=record.pk).exists()


@pytest.mark.django_db
def test_non_admin_get_gets_403_not_405(client):
    # admin_required runs before require_POST (same order as
    # deactivate_chore, #10): a non-admin session must be denied with 403
    # regardless of method, not let a GET fall through to a 405 first.
    member = FamilyMember.objects.create(name="Bob", is_admin=False)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = _make_chore(owner)
    record = CompletionRecord.objects.create(chore=chore, completed_by=owner)
    _log_in_as(client, member)

    response = client.get(reverse("delete_completion_record", args=[record.pk]))

    assert response.status_code == 403
    assert CompletionRecord.objects.filter(pk=record.pk).exists()


@pytest.mark.django_db
def test_get_returns_405(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = _make_chore(owner)
    record = CompletionRecord.objects.create(chore=chore, completed_by=owner)
    _log_in_as(client, admin)

    response = client.get(reverse("delete_completion_record", args=[record.pk]))

    assert response.status_code == 405
    assert CompletionRecord.objects.filter(pk=record.pk).exists()


@pytest.mark.django_db
def test_nonexistent_record_returns_404(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    _log_in_as(client, admin)

    response = client.post(reverse("delete_completion_record", args=[999999]))

    assert response.status_code == 404


@pytest.mark.django_db
def test_valid_delete_removes_record_and_redirects(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = _make_chore(owner)
    record = CompletionRecord.objects.create(chore=chore, completed_by=owner)
    _log_in_as(client, admin)

    response = client.post(reverse("delete_completion_record", args=[record.pk]))

    assert response.status_code == 302
    assert response.url == reverse("completed_chores")
    assert not CompletionRecord.objects.filter(pk=record.pk).exists()
    assert Chore.objects.filter(pk=chore.pk).exists()


@pytest.mark.django_db
def test_deleting_sole_record_reopens_one_time_chore_in_personal_chores(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = _make_chore(owner, title="Dishes")
    record = CompletionRecord.objects.create(chore=chore, completed_by=owner)
    _log_in_as(client, admin)

    response = client.post(reverse("delete_completion_record", args=[record.pk]))
    assert response.status_code == 302

    _log_in_as(client, owner)
    personal_response = client.get(reverse("personal_chores"))
    assert "Dishes" in personal_response.content.decode()


@pytest.mark.django_db
def test_deleting_sole_record_reopens_one_time_chore_in_family_overview(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = _make_chore(owner, title="Dishes")
    record = CompletionRecord.objects.create(chore=chore, completed_by=owner)
    _log_in_as(client, admin)

    response = client.post(reverse("delete_completion_record", args=[record.pk]))
    assert response.status_code == 302

    overview_response = client.get(reverse("family_overview"))
    assert "Dishes" in overview_response.content.decode()


@pytest.mark.django_db
def test_deleting_recurring_occurrence_record_leaves_next_occurrence_untouched(
    client,
):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = _make_chore(
        owner,
        title="Vacuum",
        chore_type=Chore.ChoreType.RECURRING,
        recurrence=Chore.Recurrence.WEEKLY,
    )
    _log_in_as(client, owner)
    complete_response = client.post(reverse("complete_chore", args=[chore.pk]))
    assert complete_response.status_code == 302

    next_chore = Chore.objects.exclude(pk=chore.pk).get()
    record = CompletionRecord.objects.get(chore=chore)

    _log_in_as(client, admin)
    delete_response = client.post(
        reverse("delete_completion_record", args=[record.pk])
    )
    assert delete_response.status_code == 302

    # The completed row's record is gone, so that row reopens...
    assert not CompletionRecord.objects.filter(chore=chore).exists()
    # ...while the newer, already-generated occurrence is completely
    # untouched: still active, still no record of its own.
    next_chore.refresh_from_db()
    assert next_chore.is_active is True
    assert not CompletionRecord.objects.filter(chore=next_chore).exists()
    assert Chore.objects.count() == 2

    # Both rows are now open simultaneously in the family overview.
    overview_response = client.get(reverse("family_overview"))
    content = overview_response.content.decode()
    assert content.count("Vacuum") == 2


@pytest.mark.django_db
def test_delete_does_not_touch_chore_is_active(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = _make_chore(owner)
    record = CompletionRecord.objects.create(chore=chore, completed_by=owner)
    _log_in_as(client, admin)

    response = client.post(reverse("delete_completion_record", args=[record.pk]))

    assert response.status_code == 302
    chore.refresh_from_db()
    assert chore.is_active is True
