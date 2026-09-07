import datetime

import pytest
from django.utils import timezone

from chores.models import Chore, CompletionRecord, FamilyMember


@pytest.mark.django_db
def test_family_member_chore_and_completion_record_survive_db_round_trip():
    member = FamilyMember.objects.create(name="Frank", is_admin=True)

    chore = Chore.objects.create(
        title="Mow the lawn",
        owner=member,
        priority=Chore.Priority.IMPORTANT,
        chore_type=Chore.ChoreType.RECURRING,
        due_date=datetime.date(2026, 9, 20),
        recurrence=Chore.Recurrence.WEEKLY,
        is_active=True,
    )

    completed_at = timezone.make_aware(datetime.datetime(2026, 9, 7, 9, 0, 0))
    record = CompletionRecord.objects.create(
        chore=chore, completed_by=member, completed_at=completed_at
    )

    # Re-fetch each object by primary key via a fresh queryset, rather than
    # reusing the Python variables created above, to prove the data actually
    # round-trips through the database.
    fetched_member = FamilyMember.objects.get(pk=member.pk)
    fetched_chore = Chore.objects.get(pk=chore.pk)
    fetched_record = CompletionRecord.objects.get(pk=record.pk)

    assert fetched_member.name == "Frank"
    assert fetched_member.is_admin is True

    assert fetched_chore.title == "Mow the lawn"
    assert fetched_chore.owner_id == member.pk
    assert fetched_chore.priority == Chore.Priority.IMPORTANT
    assert fetched_chore.chore_type == Chore.ChoreType.RECURRING
    assert fetched_chore.due_date == datetime.date(2026, 9, 20)
    assert fetched_chore.recurrence == Chore.Recurrence.WEEKLY
    assert fetched_chore.is_active is True

    assert fetched_record.chore_id == chore.pk
    assert fetched_record.completed_by_id == member.pk
    assert fetched_record.completed_at == completed_at
