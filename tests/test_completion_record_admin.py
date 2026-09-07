import datetime

import pytest

from chores.models import Chore, CompletionRecord, FamilyMember


@pytest.mark.django_db
def test_completion_record_registered_in_admin_list_display():
    from django.contrib import admin

    assert CompletionRecord in admin.site._registry
    model_admin = admin.site._registry[CompletionRecord]
    assert model_admin.list_display == ("chore", "completed_by", "completed_at")


@pytest.mark.django_db
def test_create_completion_record_via_admin(admin_client):
    owner = FamilyMember.objects.create(name="Fran")
    chore = Chore.objects.create(
        title="Wash dishes",
        owner=owner,
        chore_type=Chore.ChoreType.ONE_TIME,
        due_date=datetime.date(2026, 9, 8),
    )

    response = admin_client.post(
        "/admin/chores/completionrecord/add/",
        {
            "chore": chore.pk,
            "completed_by": owner.pk,
            "completed_at_0": "2026-09-08",
            "completed_at_1": "10:00:00",
        },
    )

    assert response.status_code == 302
    record = CompletionRecord.objects.get(chore=chore)
    assert record.completed_by_id == owner.pk


@pytest.mark.django_db
def test_completed_at_is_editable_via_admin(admin_client):
    owner = FamilyMember.objects.create(name="Gina")
    chore = Chore.objects.create(
        title="Sweep floor",
        owner=owner,
        chore_type=Chore.ChoreType.ONE_TIME,
        due_date=datetime.date(2026, 9, 8),
    )
    record = CompletionRecord.objects.create(chore=chore, completed_by=owner)

    response = admin_client.post(
        f"/admin/chores/completionrecord/{record.pk}/change/",
        {
            "chore": chore.pk,
            "completed_by": owner.pk,
            "completed_at_0": "2026-09-01",
            "completed_at_1": "09:15:00",
        },
    )

    assert response.status_code == 302
    record.refresh_from_db()
    assert record.completed_at.isoformat().startswith("2026-09-01T09:15:00")
