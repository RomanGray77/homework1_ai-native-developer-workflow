"""Tests for chores.views.edit_completion_record (#16).

The view is gated by admin_required (#6), same shape as edit_chore (#9):
GET+POST, not POST-only. The access-control tests here mirror
tests/test_edit_chore.py's contract (no session -> redirect to
select_member, non-admin session -> 403) against the real
"edit_completion_record" URL. The rest covers: GET pre-fills the form with
the record's current completed_by/completed_at, a valid POST updates only
those two fields (never the chore FK, never Chore.is_active, never
retriggering #15's _generate_next_occurrence), an invalid POST re-renders
with errors, and a nonexistent pk is a 404 for both GET and POST.
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
def test_no_session_redirects_to_select_member(client):
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = _make_chore(owner)
    record = CompletionRecord.objects.create(chore=chore, completed_by=owner)

    response = client.get(reverse("edit_completion_record", args=[record.pk]))

    assert response.status_code == 302
    assert response.url == reverse("select_member")


@pytest.mark.django_db
def test_non_admin_gets_403(client):
    member = FamilyMember.objects.create(name="Bob", is_admin=False)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = _make_chore(owner)
    record = CompletionRecord.objects.create(chore=chore, completed_by=owner)
    _log_in_as(client, member)

    response = client.get(reverse("edit_completion_record", args=[record.pk]))

    assert response.status_code == 403


@pytest.mark.django_db
def test_non_admin_post_gets_403(client):
    member = FamilyMember.objects.create(name="Bob", is_admin=False)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = _make_chore(owner)
    record = CompletionRecord.objects.create(chore=chore, completed_by=owner)
    _log_in_as(client, member)

    response = client.post(
        reverse("edit_completion_record", args=[record.pk]),
        {"completed_by": owner.pk, "completed_at": "2026-09-01 09:00:00"},
    )

    assert response.status_code == 403
    record.refresh_from_db()
    assert record.completed_by_id == owner.pk


@pytest.mark.django_db
def test_nonexistent_record_get_returns_404(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    _log_in_as(client, admin)

    response = client.get(reverse("edit_completion_record", args=[999999]))

    assert response.status_code == 404


@pytest.mark.django_db
def test_nonexistent_record_post_returns_404(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    _log_in_as(client, admin)

    response = client.post(
        reverse("edit_completion_record", args=[999999]),
        {"completed_by": owner.pk, "completed_at": "2026-09-01 09:00:00"},
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_admin_get_renders_prefilled_form(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = _make_chore(owner)
    completed_at = datetime.datetime(2026, 9, 1, 12, 0, tzinfo=datetime.timezone.utc)
    record = CompletionRecord.objects.create(
        chore=chore, completed_by=owner, completed_at=completed_at
    )
    _log_in_as(client, admin)

    response = client.get(reverse("edit_completion_record", args=[record.pk]))

    assert response.status_code == 200
    content = response.content.decode()
    assert "<form" in content
    assert 'name="chore"' not in content
    for field in ("completed_by", "completed_at"):
        assert field in content
    form = response.context["form"]
    assert form.initial["completed_by"] == owner.pk
    assert form.initial["completed_at"] == completed_at


@pytest.mark.django_db
def test_valid_edit_updates_completed_by(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    correct_completer = FamilyMember.objects.create(name="Evan", is_admin=False)
    chore = _make_chore(owner)
    completed_at = datetime.datetime(2026, 9, 1, 12, 0, tzinfo=datetime.timezone.utc)
    record = CompletionRecord.objects.create(
        chore=chore, completed_by=owner, completed_at=completed_at
    )
    _log_in_as(client, admin)

    response = client.post(
        reverse("edit_completion_record", args=[record.pk]),
        {
            "completed_by": correct_completer.pk,
            "completed_at": "2026-09-01 12:00:00",
        },
    )

    assert response.status_code == 302
    assert response.url == reverse("completed_chores")
    record.refresh_from_db()
    assert record.completed_by_id == correct_completer.pk


@pytest.mark.django_db
def test_valid_edit_updates_completed_at(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = _make_chore(owner)
    record = CompletionRecord.objects.create(
        chore=chore,
        completed_by=owner,
        completed_at=datetime.datetime(2026, 9, 1, 12, 0, tzinfo=datetime.timezone.utc),
    )
    _log_in_as(client, admin)

    response = client.post(
        reverse("edit_completion_record", args=[record.pk]),
        {
            "completed_by": owner.pk,
            "completed_at": "2026-08-25 09:15:00",
        },
    )

    assert response.status_code == 302
    record.refresh_from_db()
    assert record.completed_at.isoformat().startswith("2026-08-25T09:15:00")


@pytest.mark.django_db
def test_invalid_edit_missing_completed_by_rerenders_with_errors(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = _make_chore(owner)
    original_completed_at = datetime.datetime(
        2026, 9, 1, 12, 0, tzinfo=datetime.timezone.utc
    )
    record = CompletionRecord.objects.create(
        chore=chore, completed_by=owner, completed_at=original_completed_at
    )
    _log_in_as(client, admin)

    response = client.post(
        reverse("edit_completion_record", args=[record.pk]),
        {"completed_by": "", "completed_at": "2026-09-01 12:00:00"},
    )

    assert response.status_code == 200
    assert "completed_by" in response.context["form"].errors
    record.refresh_from_db()
    assert record.completed_by_id == owner.pk
    assert record.completed_at == original_completed_at


@pytest.mark.django_db
def test_edit_does_not_reassign_chore_fk(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = _make_chore(owner)
    other_chore = _make_chore(owner, title="Other chore")
    record = CompletionRecord.objects.create(chore=chore, completed_by=owner)
    _log_in_as(client, admin)

    response = client.post(
        reverse("edit_completion_record", args=[record.pk]),
        {
            "completed_by": owner.pk,
            "completed_at": "2026-09-01 12:00:00",
            # Even if a "chore" field were tampered into the POST body, the
            # form has no such field, so it must have no effect.
            "chore": other_chore.pk,
        },
    )

    assert response.status_code == 302
    record.refresh_from_db()
    assert record.chore_id == chore.pk


@pytest.mark.django_db
def test_edit_does_not_touch_chore_is_active_or_generate_next_occurrence(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = _make_chore(
        owner,
        title="Vacuum",
        chore_type=Chore.ChoreType.RECURRING,
        recurrence=Chore.Recurrence.WEEKLY,
    )
    record = CompletionRecord.objects.create(chore=chore, completed_by=owner)
    _log_in_as(client, admin)

    response = client.post(
        reverse("edit_completion_record", args=[record.pk]),
        {"completed_by": owner.pk, "completed_at": "2026-09-01 12:00:00"},
    )

    assert response.status_code == 302
    chore.refresh_from_db()
    assert chore.is_active is True
    # No next occurrence should have been generated by this correction.
    assert Chore.objects.count() == 1
