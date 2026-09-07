import datetime

import pytest
from django.db.models import ProtectedError
from django.utils import timezone

from chores.models import Chore, CompletionRecord, FamilyMember


def _make_chore(owner):
    return Chore.objects.create(
        title="Take out the trash",
        owner=owner,
        chore_type=Chore.ChoreType.ONE_TIME,
        due_date=datetime.date(2026, 9, 10),
    )


@pytest.mark.django_db
def test_create_completion_record_defaults_completed_at_to_now():
    owner = FamilyMember.objects.create(name="Alice")
    chore = _make_chore(owner)

    before = timezone.now()
    record = CompletionRecord.objects.create(chore=chore, completed_by=owner)
    after = timezone.now()

    record.refresh_from_db()
    assert record.chore_id == chore.pk
    assert record.completed_by_id == owner.pk
    assert before <= record.completed_at <= after


@pytest.mark.django_db
def test_completed_at_can_be_set_explicitly_and_corrected_afterward():
    owner = FamilyMember.objects.create(name="Bob")
    chore = _make_chore(owner)
    explicit_time = timezone.make_aware(datetime.datetime(2026, 9, 1, 12, 0, 0))

    record = CompletionRecord.objects.create(
        chore=chore, completed_by=owner, completed_at=explicit_time
    )
    record.refresh_from_db()
    assert record.completed_at == explicit_time

    corrected_time = timezone.make_aware(datetime.datetime(2026, 9, 2, 8, 30, 0))
    record.completed_at = corrected_time
    record.save()

    record.refresh_from_db()
    assert record.completed_at == corrected_time


@pytest.mark.django_db
def test_chore_can_have_multiple_completion_records():
    owner = FamilyMember.objects.create(name="Carol")
    chore = _make_chore(owner)

    CompletionRecord.objects.create(chore=chore, completed_by=owner)
    CompletionRecord.objects.create(chore=chore, completed_by=owner)

    assert CompletionRecord.objects.filter(chore=chore).count() == 2


@pytest.mark.django_db
def test_deleting_chore_with_completion_record_is_protected():
    owner = FamilyMember.objects.create(name="Dana")
    chore = _make_chore(owner)
    CompletionRecord.objects.create(chore=chore, completed_by=owner)

    with pytest.raises(ProtectedError):
        chore.delete()

    assert Chore.objects.filter(pk=chore.pk).exists()


@pytest.mark.django_db
def test_deleting_family_member_with_completion_record_is_protected():
    owner = FamilyMember.objects.create(name="Evan")
    chore = _make_chore(owner)
    CompletionRecord.objects.create(chore=chore, completed_by=owner)

    with pytest.raises(ProtectedError):
        owner.delete()

    assert FamilyMember.objects.filter(pk=owner.pk).exists()
