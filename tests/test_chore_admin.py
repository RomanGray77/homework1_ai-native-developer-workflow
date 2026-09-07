import pytest

from chores.models import Chore, FamilyMember


@pytest.mark.django_db
def test_chore_registered_in_admin_list_display():
    from django.contrib import admin

    assert Chore in admin.site._registry
    model_admin = admin.site._registry[Chore]
    assert model_admin.list_display == (
        "title",
        "owner",
        "chore_type",
        "priority",
        "due_date",
        "recurrence",
        "is_active",
    )


@pytest.mark.django_db
def test_create_one_time_chore_via_admin(admin_client):
    owner = FamilyMember.objects.create(name="Dana")

    response = admin_client.post(
        "/admin/chores/chore/add/",
        {
            "title": "Mow the lawn",
            "owner": owner.pk,
            "priority": Chore.Priority.NORMAL,
            "chore_type": Chore.ChoreType.ONE_TIME,
            "due_date": "2026-09-15",
            "recurrence": "",
            "is_active": "on",
        },
    )

    assert response.status_code == 302
    chore = Chore.objects.get(title="Mow the lawn")
    assert chore.due_date.isoformat() == "2026-09-15"
    assert chore.recurrence in ("", None)


@pytest.mark.django_db
def test_create_recurring_chore_via_admin(admin_client):
    owner = FamilyMember.objects.create(name="Evan")

    response = admin_client.post(
        "/admin/chores/chore/add/",
        {
            "title": "Vacuum living room",
            "owner": owner.pk,
            "priority": Chore.Priority.IMPORTANT,
            "chore_type": Chore.ChoreType.RECURRING,
            "due_date": "",
            "recurrence": Chore.Recurrence.MONTHLY,
            "is_active": "on",
        },
    )

    assert response.status_code == 302
    chore = Chore.objects.get(title="Vacuum living room")
    assert chore.due_date is None
    assert chore.recurrence == Chore.Recurrence.MONTHLY
