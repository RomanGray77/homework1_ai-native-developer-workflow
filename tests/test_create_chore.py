"""Tests for chores.views.create_chore (#8).

The view is gated by admin_required (#6), so the access-control tests here
mirror tests/test_admin_required.py's contract (no session -> redirect to
select_member, non-admin session -> 403) against the real "create_chore"
URL. The rest covers the form's validation rules from _docs/architecture.md
(due_date is one-time only, recurrence is recurring only) and the
tampered-owner-id handling used the same way as #7's member selection.
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
    response = client.get(reverse("create_chore"))

    assert response.status_code == 302
    assert response.url == reverse("select_member")


@pytest.mark.django_db
def test_non_admin_gets_403(client):
    member = FamilyMember.objects.create(name="Bob", is_admin=False)
    _log_in_as(client, member)

    response = client.get(reverse("create_chore"))

    assert response.status_code == 403


@pytest.mark.django_db
def test_admin_get_renders_form(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    _log_in_as(client, admin)

    response = client.get(reverse("create_chore"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "<form" in content
    for field in ("title", "owner", "priority", "chore_type", "due_date", "recurrence"):
        assert field in content


@pytest.mark.django_db
def test_admin_post_valid_one_time_chore_creates_it(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    _log_in_as(client, admin)

    response = client.post(
        reverse("create_chore"),
        {
            "title": "Mow the lawn",
            "owner": owner.pk,
            "priority": Chore.Priority.NORMAL,
            "chore_type": Chore.ChoreType.ONE_TIME,
            "due_date": "",
            "recurrence": "",
        },
    )

    assert response.status_code == 302
    # POST_CREATE_REDIRECT_URL_NAME (#12) now points at family_overview,
    # not the "health" placeholder used before #12 shipped.
    assert response.url == reverse("family_overview")
    chore = Chore.objects.get(title="Mow the lawn")
    assert chore.owner == owner
    assert chore.chore_type == Chore.ChoreType.ONE_TIME
    assert chore.due_date is None
    assert chore.recurrence is None
    assert chore.is_active is True
    assert not CompletionRecord.objects.filter(chore=chore).exists()


@pytest.mark.django_db
def test_admin_post_valid_recurring_chore_creates_it(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    owner = FamilyMember.objects.create(name="Evan", is_admin=False)
    _log_in_as(client, admin)

    response = client.post(
        reverse("create_chore"),
        {
            "title": "Vacuum living room",
            "owner": owner.pk,
            "priority": Chore.Priority.IMPORTANT,
            "chore_type": Chore.ChoreType.RECURRING,
            "due_date": "",
            "recurrence": Chore.Recurrence.MONTHLY,
        },
    )

    assert response.status_code == 302
    assert response.url == reverse("family_overview")
    chore = Chore.objects.get(title="Vacuum living room")
    assert chore.owner == owner
    assert chore.chore_type == Chore.ChoreType.RECURRING
    assert chore.due_date is None
    assert chore.recurrence == Chore.Recurrence.MONTHLY
    assert chore.is_active is True
    assert not CompletionRecord.objects.filter(chore=chore).exists()


@pytest.mark.django_db
def test_recurring_without_recurrence_rejected(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    _log_in_as(client, admin)

    response = client.post(
        reverse("create_chore"),
        {
            "title": "Bad recurring",
            "owner": owner.pk,
            "priority": Chore.Priority.NORMAL,
            "chore_type": Chore.ChoreType.RECURRING,
            "due_date": "",
            "recurrence": "",
        },
    )

    assert response.status_code == 200
    assert not Chore.objects.filter(title="Bad recurring").exists()
    assert "recurrence" in response.context["form"].errors


@pytest.mark.django_db
def test_recurring_with_due_date_rejected(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    _log_in_as(client, admin)

    response = client.post(
        reverse("create_chore"),
        {
            "title": "Recurring with due date",
            "owner": owner.pk,
            "priority": Chore.Priority.NORMAL,
            "chore_type": Chore.ChoreType.RECURRING,
            "due_date": "2026-09-15",
            "recurrence": Chore.Recurrence.DAILY,
        },
    )

    assert response.status_code == 200
    assert not Chore.objects.filter(title="Recurring with due date").exists()
    assert "due_date" in response.context["form"].errors


@pytest.mark.django_db
def test_one_time_with_recurrence_rejected(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    _log_in_as(client, admin)

    response = client.post(
        reverse("create_chore"),
        {
            "title": "One time with recurrence",
            "owner": owner.pk,
            "priority": Chore.Priority.NORMAL,
            "chore_type": Chore.ChoreType.ONE_TIME,
            "due_date": "",
            "recurrence": Chore.Recurrence.WEEKLY,
        },
    )

    assert response.status_code == 200
    assert not Chore.objects.filter(title="One time with recurrence").exists()
    assert "recurrence" in response.context["form"].errors


@pytest.mark.django_db
def test_one_time_with_no_due_date_succeeds(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    _log_in_as(client, admin)

    response = client.post(
        reverse("create_chore"),
        {
            "title": "Open ended one-time",
            "owner": owner.pk,
            "priority": Chore.Priority.NORMAL,
            "chore_type": Chore.ChoreType.ONE_TIME,
            "due_date": "",
            "recurrence": "",
        },
    )

    assert response.status_code == 302
    chore = Chore.objects.get(title="Open ended one-time")
    assert chore.due_date is None
    assert chore.is_active is True


@pytest.mark.django_db
def test_missing_title_rejected(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    _log_in_as(client, admin)

    response = client.post(
        reverse("create_chore"),
        {
            "title": "",
            "owner": owner.pk,
            "priority": Chore.Priority.NORMAL,
            "chore_type": Chore.ChoreType.ONE_TIME,
            "due_date": "",
            "recurrence": "",
        },
    )

    assert response.status_code == 200
    assert Chore.objects.count() == 0
    assert "title" in response.context["form"].errors


@pytest.mark.django_db
def test_missing_owner_rejected(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    _log_in_as(client, admin)

    response = client.post(
        reverse("create_chore"),
        {
            "title": "No owner",
            "owner": "",
            "priority": Chore.Priority.NORMAL,
            "chore_type": Chore.ChoreType.ONE_TIME,
            "due_date": "",
            "recurrence": "",
        },
    )

    assert response.status_code == 200
    assert Chore.objects.count() == 0
    assert "owner" in response.context["form"].errors


@pytest.mark.django_db
def test_missing_chore_type_rejected(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    _log_in_as(client, admin)

    response = client.post(
        reverse("create_chore"),
        {
            "title": "No chore type",
            "owner": owner.pk,
            "priority": Chore.Priority.NORMAL,
            "chore_type": "",
            "due_date": "",
            "recurrence": "",
        },
    )

    assert response.status_code == 200
    assert Chore.objects.count() == 0
    assert "chore_type" in response.context["form"].errors


@pytest.mark.django_db
def test_invalid_chore_type_rejected(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    _log_in_as(client, admin)

    response = client.post(
        reverse("create_chore"),
        {
            "title": "Bad chore type",
            "owner": owner.pk,
            "priority": Chore.Priority.NORMAL,
            "chore_type": "sometimes",
            "due_date": "",
            "recurrence": "",
        },
    )

    assert response.status_code == 200
    assert Chore.objects.count() == 0
    assert "chore_type" in response.context["form"].errors


@pytest.mark.django_db
def test_invalid_owner_id_rejected_not_500(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    _log_in_as(client, admin)

    response = client.post(
        reverse("create_chore"),
        {
            "title": "Tampered owner",
            "owner": 999999,
            "priority": Chore.Priority.NORMAL,
            "chore_type": Chore.ChoreType.ONE_TIME,
            "due_date": "",
            "recurrence": "",
        },
    )

    assert response.status_code == 200
    assert Chore.objects.count() == 0
    assert "owner" in response.context["form"].errors
