"""Tests for chores.views.edit_chore (#9).

The view is gated by admin_required (#6), so the access-control tests here
mirror tests/test_create_chore.py's contract (no session -> redirect to
select_member, non-admin session -> 403) against the real "edit_chore" URL.
The rest covers: a valid edit persists new values, chore_type can never be
changed via this form, the due_date/recurrence mutual-exclusivity rule is
enforced using the chore's existing (unchangeable) chore_type, editing never
touches an existing CompletionRecord, and a nonexistent pk is a 404.
"""

import pytest
from django.urls import reverse

from chores.models import Chore, CompletionRecord, FamilyMember


def _log_in_as(client, member):
    session = client.session
    session["family_member_id"] = member.pk
    session.save()


@pytest.mark.django_db
def test_no_session_redirects_to_select_member(client):
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = Chore.objects.create(
        title="Dishes",
        owner=owner,
        chore_type=Chore.ChoreType.ONE_TIME,
    )

    response = client.get(reverse("edit_chore", args=[chore.pk]))

    assert response.status_code == 302
    assert response.url == reverse("select_member")


@pytest.mark.django_db
def test_non_admin_gets_403(client):
    member = FamilyMember.objects.create(name="Bob", is_admin=False)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = Chore.objects.create(
        title="Dishes",
        owner=owner,
        chore_type=Chore.ChoreType.ONE_TIME,
    )
    _log_in_as(client, member)

    response = client.get(reverse("edit_chore", args=[chore.pk]))

    assert response.status_code == 403


@pytest.mark.django_db
def test_nonexistent_chore_get_returns_404(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    _log_in_as(client, admin)

    response = client.get(reverse("edit_chore", args=[999999]))

    assert response.status_code == 404


@pytest.mark.django_db
def test_nonexistent_chore_post_returns_404(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    _log_in_as(client, admin)

    response = client.post(
        reverse("edit_chore", args=[999999]),
        {
            "title": "Whatever",
            "owner": owner.pk,
            "priority": Chore.Priority.NORMAL,
            "due_date": "",
            "recurrence": "",
        },
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_admin_get_renders_prefilled_form(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = Chore.objects.create(
        title="Mow the lawn",
        owner=owner,
        priority=Chore.Priority.IMPORTANT,
        chore_type=Chore.ChoreType.ONE_TIME,
        due_date="2026-09-20",
    )
    _log_in_as(client, admin)

    response = client.get(reverse("edit_chore", args=[chore.pk]))

    assert response.status_code == 200
    content = response.content.decode()
    assert "<form" in content
    assert "chore_type" not in content
    for field in ("title", "owner", "priority", "due_date", "recurrence"):
        assert field in content
    form = response.context["form"]
    assert form.initial["title"] == "Mow the lawn"
    assert form.initial["owner"] == owner.pk
    assert form.initial["priority"] == Chore.Priority.IMPORTANT


@pytest.mark.django_db
def test_valid_edit_updates_fields(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    new_owner = FamilyMember.objects.create(name="Evan", is_admin=False)
    chore = Chore.objects.create(
        title="Mow the lawn",
        owner=owner,
        priority=Chore.Priority.NORMAL,
        chore_type=Chore.ChoreType.ONE_TIME,
        due_date="2026-09-20",
    )
    _log_in_as(client, admin)

    response = client.post(
        reverse("edit_chore", args=[chore.pk]),
        {
            "title": "Mow the back lawn",
            "owner": new_owner.pk,
            "priority": Chore.Priority.IMPORTANT,
            "due_date": "2026-10-01",
            "recurrence": "",
        },
    )

    assert response.status_code == 302
    assert response.url == reverse("health")
    chore.refresh_from_db()
    assert chore.title == "Mow the back lawn"
    assert chore.owner == new_owner
    assert chore.priority == Chore.Priority.IMPORTANT
    assert str(chore.due_date) == "2026-10-01"
    assert chore.recurrence is None
    assert chore.chore_type == Chore.ChoreType.ONE_TIME


@pytest.mark.django_db
def test_valid_edit_updates_recurrence_on_recurring_chore(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = Chore.objects.create(
        title="Vacuum",
        owner=owner,
        priority=Chore.Priority.NORMAL,
        chore_type=Chore.ChoreType.RECURRING,
        recurrence=Chore.Recurrence.WEEKLY,
    )
    _log_in_as(client, admin)

    response = client.post(
        reverse("edit_chore", args=[chore.pk]),
        {
            "title": "Vacuum",
            "owner": owner.pk,
            "priority": Chore.Priority.NORMAL,
            "due_date": "",
            "recurrence": Chore.Recurrence.MONTHLY,
        },
    )

    assert response.status_code == 302
    chore.refresh_from_db()
    assert chore.recurrence == Chore.Recurrence.MONTHLY
    assert chore.chore_type == Chore.ChoreType.RECURRING


@pytest.mark.django_db
def test_submitted_chore_type_has_no_effect(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = Chore.objects.create(
        title="Mow the lawn",
        owner=owner,
        chore_type=Chore.ChoreType.ONE_TIME,
        due_date="2026-09-20",
    )
    _log_in_as(client, admin)

    response = client.post(
        reverse("edit_chore", args=[chore.pk]),
        {
            "title": "Mow the lawn",
            "owner": owner.pk,
            "priority": Chore.Priority.NORMAL,
            "chore_type": Chore.ChoreType.RECURRING,
            "due_date": "2026-09-20",
            "recurrence": "",
        },
    )

    assert response.status_code == 302
    chore.refresh_from_db()
    assert chore.chore_type == Chore.ChoreType.ONE_TIME
    assert chore.due_date is not None


@pytest.mark.django_db
def test_due_date_rejected_on_recurring_chore(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = Chore.objects.create(
        title="Vacuum",
        owner=owner,
        chore_type=Chore.ChoreType.RECURRING,
        recurrence=Chore.Recurrence.WEEKLY,
    )
    _log_in_as(client, admin)

    response = client.post(
        reverse("edit_chore", args=[chore.pk]),
        {
            "title": "Vacuum",
            "owner": owner.pk,
            "priority": Chore.Priority.NORMAL,
            "due_date": "2026-09-20",
            "recurrence": Chore.Recurrence.WEEKLY,
        },
    )

    assert response.status_code == 200
    assert "due_date" in response.context["form"].errors
    chore.refresh_from_db()
    assert chore.due_date is None


@pytest.mark.django_db
def test_recurrence_rejected_on_one_time_chore(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = Chore.objects.create(
        title="Mow the lawn",
        owner=owner,
        chore_type=Chore.ChoreType.ONE_TIME,
        due_date="2026-09-20",
    )
    _log_in_as(client, admin)

    response = client.post(
        reverse("edit_chore", args=[chore.pk]),
        {
            "title": "Mow the lawn",
            "owner": owner.pk,
            "priority": Chore.Priority.NORMAL,
            "due_date": "2026-09-20",
            "recurrence": Chore.Recurrence.WEEKLY,
        },
    )

    assert response.status_code == 200
    assert "recurrence" in response.context["form"].errors
    chore.refresh_from_db()
    assert chore.recurrence is None


@pytest.mark.django_db
def test_tampered_owner_id_rejected_not_500(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = Chore.objects.create(
        title="Mow the lawn",
        owner=owner,
        chore_type=Chore.ChoreType.ONE_TIME,
    )
    _log_in_as(client, admin)

    response = client.post(
        reverse("edit_chore", args=[chore.pk]),
        {
            "title": "Mow the lawn",
            "owner": 999999,
            "priority": Chore.Priority.NORMAL,
            "due_date": "",
            "recurrence": "",
        },
    )

    assert response.status_code == 200
    assert "owner" in response.context["form"].errors
    chore.refresh_from_db()
    assert chore.owner == owner


@pytest.mark.django_db
def test_edit_does_not_modify_existing_completion_record(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    new_owner = FamilyMember.objects.create(name="Evan", is_admin=False)
    chore = Chore.objects.create(
        title="Mow the lawn",
        owner=owner,
        priority=Chore.Priority.NORMAL,
        chore_type=Chore.ChoreType.ONE_TIME,
    )
    record = CompletionRecord.objects.create(chore=chore, completed_by=owner)
    original_chore_id = record.chore_id
    original_completed_by_id = record.completed_by_id
    original_completed_at = record.completed_at
    _log_in_as(client, admin)

    response = client.post(
        reverse("edit_chore", args=[chore.pk]),
        {
            "title": "Mow the lawn",
            "owner": new_owner.pk,
            "priority": Chore.Priority.IMPORTANT,
            "due_date": "",
            "recurrence": "",
        },
    )

    assert response.status_code == 302
    record.refresh_from_db()
    assert record.chore_id == original_chore_id
    assert record.completed_by_id == original_completed_by_id
    assert record.completed_at == original_completed_at


@pytest.mark.django_db
def test_missing_title_rejected(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = Chore.objects.create(
        title="Mow the lawn",
        owner=owner,
        chore_type=Chore.ChoreType.ONE_TIME,
    )
    _log_in_as(client, admin)

    response = client.post(
        reverse("edit_chore", args=[chore.pk]),
        {
            "title": "",
            "owner": owner.pk,
            "priority": Chore.Priority.NORMAL,
            "due_date": "",
            "recurrence": "",
        },
    )

    assert response.status_code == 200
    assert "title" in response.context["form"].errors
    chore.refresh_from_db()
    assert chore.title == "Mow the lawn"
