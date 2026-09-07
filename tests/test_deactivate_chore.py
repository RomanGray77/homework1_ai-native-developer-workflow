"""Tests for chores.views.deactivate_chore and Chore.objects.active() (#10).

The view is gated by admin_required (#6), so the access-control tests here
mirror tests/test_create_chore.py's and tests/test_edit_chore.py's contract
(no session -> redirect to select_member, non-admin session -> 403) against
the real "deactivate_chore" URL. It is also POST-only (GET -> 405, no
confirmation page in this task). The rest covers: is_active flips to False
without deleting the row, Chore.objects.active() excludes a deactivated
chore and includes an active one, an existing CompletionRecord is left
completely untouched, re-deactivating an already-inactive chore is a no-op
rather than an error, and a nonexistent pk is a 404.
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

    response = client.get(reverse("deactivate_chore", args=[chore.pk]))

    assert response.status_code == 302
    assert response.url == reverse("select_member")


@pytest.mark.django_db
def test_non_admin_gets_403(client):
    member = FamilyMember.objects.create(name="Bob", is_admin=False)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = _make_chore(owner)
    _log_in_as(client, member)

    response = client.post(reverse("deactivate_chore", args=[chore.pk]))

    assert response.status_code == 403
    chore.refresh_from_db()
    assert chore.is_active is True


@pytest.mark.django_db
def test_get_returns_405(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = _make_chore(owner)
    _log_in_as(client, admin)

    response = client.get(reverse("deactivate_chore", args=[chore.pk]))

    assert response.status_code == 405
    chore.refresh_from_db()
    assert chore.is_active is True


@pytest.mark.django_db
def test_nonexistent_chore_returns_404(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    _log_in_as(client, admin)

    response = client.post(reverse("deactivate_chore", args=[999999]))

    assert response.status_code == 404


@pytest.mark.django_db
def test_admin_post_deactivates_chore_without_deleting_it(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = _make_chore(owner)
    _log_in_as(client, admin)

    response = client.post(reverse("deactivate_chore", args=[chore.pk]))

    assert response.status_code == 302
    assert response.url == reverse("personal_chores")
    assert Chore.objects.filter(pk=chore.pk).exists()
    chore.refresh_from_db()
    assert chore.is_active is False


@pytest.mark.django_db
def test_active_manager_excludes_deactivated_and_includes_active(client):
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    active_chore = _make_chore(owner, title="Still active")
    deactivated_chore = _make_chore(owner, title="Gone", is_active=False)

    active_titles = set(Chore.objects.active().values_list("title", flat=True))

    assert active_chore.title in active_titles
    assert deactivated_chore.title not in active_titles


@pytest.mark.django_db
def test_deactivation_leaves_completion_record_untouched(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = _make_chore(owner)
    record = CompletionRecord.objects.create(chore=chore, completed_by=owner)
    original_chore_id = record.chore_id
    original_completed_by_id = record.completed_by_id
    original_completed_at = record.completed_at
    _log_in_as(client, admin)

    response = client.post(reverse("deactivate_chore", args=[chore.pk]))

    assert response.status_code == 302
    record.refresh_from_db()
    assert record.chore_id == original_chore_id
    assert record.completed_by_id == original_completed_by_id
    assert record.completed_at == original_completed_at


@pytest.mark.django_db
def test_deactivating_already_inactive_chore_is_a_noop(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = _make_chore(owner, is_active=False)
    _log_in_as(client, admin)

    response = client.post(reverse("deactivate_chore", args=[chore.pk]))

    assert response.status_code == 302
    assert response.url == reverse("personal_chores")
    chore.refresh_from_db()
    assert chore.is_active is False
