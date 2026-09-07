import datetime

import pytest
from django.db.models import ProtectedError

from chores.models import Chore, FamilyMember


@pytest.mark.django_db
def test_create_one_time_chore_with_due_date_and_blank_recurrence():
    owner = FamilyMember.objects.create(name="Alice")

    chore = Chore.objects.create(
        title="Take out the trash",
        owner=owner,
        priority=Chore.Priority.NORMAL,
        chore_type=Chore.ChoreType.ONE_TIME,
        due_date=datetime.date(2026, 9, 10),
        recurrence="",
    )

    chore.refresh_from_db()
    assert chore.due_date == datetime.date(2026, 9, 10)
    assert chore.recurrence in ("", None)
    assert chore.is_active is True


@pytest.mark.django_db
def test_create_recurring_chore_with_recurrence_and_blank_due_date():
    owner = FamilyMember.objects.create(name="Bob")

    chore = Chore.objects.create(
        title="Water the plants",
        owner=owner,
        priority=Chore.Priority.IMPORTANT,
        chore_type=Chore.ChoreType.RECURRING,
        due_date=None,
        recurrence=Chore.Recurrence.WEEKLY,
    )

    chore.refresh_from_db()
    assert chore.due_date is None
    assert chore.recurrence == Chore.Recurrence.WEEKLY
    assert chore.is_active is True


@pytest.mark.django_db
def test_deleting_owner_with_chore_is_protected():
    owner = FamilyMember.objects.create(name="Carol")
    Chore.objects.create(
        title="Wash dishes",
        owner=owner,
        chore_type=Chore.ChoreType.ONE_TIME,
        due_date=datetime.date(2026, 9, 8),
    )

    with pytest.raises(ProtectedError):
        owner.delete()

    assert FamilyMember.objects.filter(pk=owner.pk).exists()
