"""Tests for chores.views.complete_chore (#13).

Unlike create_chore/edit_chore/deactivate_chore, this view has no
admin_required gate - any selected family member (admin or not) may
complete any chore, not just their own. The session check mirrors
personal_chores'/family_overview's inline pattern (missing, malformed, or
stale family_member_id -> redirect to select_member), not admin_required's
(there is no is_admin check here at all). It is POST-only (GET -> 405,
mirroring deactivate_chore), a nonexistent pk is a 404 via
get_object_or_404, and completing an already-completed chore is a no-op
identical in shape to deactivate_chore's already-inactive case: no second
CompletionRecord, no error, same redirect as success. This file also covers
the follow-through into #11/#12: a completed chore drops out of both open
lists.
"""

import pytest
from django.urls import reverse
from django.utils import timezone

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

    response = client.post(reverse("complete_chore", args=[chore.pk]))

    assert response.status_code == 302
    assert response.url == reverse("select_member")
    assert not CompletionRecord.objects.filter(chore=chore).exists()


@pytest.mark.django_db
def test_malformed_session_value_redirects_not_500(client):
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = _make_chore(owner)
    session = client.session
    session["family_member_id"] = "not-an-int"
    session.save()

    response = client.post(reverse("complete_chore", args=[chore.pk]))

    assert response.status_code == 302
    assert response.url == reverse("select_member")
    assert not CompletionRecord.objects.filter(chore=chore).exists()


@pytest.mark.django_db
def test_stale_nonexistent_session_id_redirects_not_500(client):
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = _make_chore(owner)
    session = client.session
    session["family_member_id"] = 999999
    session.save()

    response = client.post(reverse("complete_chore", args=[chore.pk]))

    assert response.status_code == 302
    assert response.url == reverse("select_member")
    assert not CompletionRecord.objects.filter(chore=chore).exists()


@pytest.mark.django_db
def test_get_returns_405(client):
    member = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = _make_chore(member)
    _log_in_as(client, member)

    response = client.get(reverse("complete_chore", args=[chore.pk]))

    assert response.status_code == 405
    assert not CompletionRecord.objects.filter(chore=chore).exists()


@pytest.mark.django_db
def test_nonexistent_chore_returns_404(client):
    member = FamilyMember.objects.create(name="Dana", is_admin=False)
    _log_in_as(client, member)

    response = client.post(reverse("complete_chore", args=[999999]))

    assert response.status_code == 404


@pytest.mark.django_db
def test_non_owner_non_admin_member_can_complete_a_chore(client):
    # No admin_required gate: a non-admin, non-owner member can complete
    # someone else's chore.
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    completer = FamilyMember.objects.create(name="Eli", is_admin=False)
    chore = _make_chore(owner)
    _log_in_as(client, completer)

    response = client.post(reverse("complete_chore", args=[chore.pk]))

    assert response.status_code == 302
    assert response.url == reverse("family_overview")
    assert CompletionRecord.objects.filter(chore=chore).count() == 1


@pytest.mark.django_db
def test_completion_record_has_correct_completed_by_and_completed_at(client):
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    completer = FamilyMember.objects.create(name="Eli", is_admin=False)
    chore = _make_chore(owner)
    _log_in_as(client, completer)

    before = timezone.now()
    response = client.post(reverse("complete_chore", args=[chore.pk]))
    after = timezone.now()

    assert response.status_code == 302
    record = CompletionRecord.objects.get(chore=chore)
    assert record.completed_by_id == completer.pk
    assert before <= record.completed_at <= after


@pytest.mark.django_db
def test_completing_already_completed_chore_is_a_noop(client):
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    first_completer = FamilyMember.objects.create(name="Eli", is_admin=False)
    second_completer = FamilyMember.objects.create(name="Frank", is_admin=False)
    chore = _make_chore(owner)
    existing_record = CompletionRecord.objects.create(
        chore=chore, completed_by=first_completer
    )
    _log_in_as(client, second_completer)

    response = client.post(reverse("complete_chore", args=[chore.pk]))

    assert response.status_code == 302
    assert response.url == reverse("family_overview")
    assert CompletionRecord.objects.filter(chore=chore).count() == 1
    remaining = CompletionRecord.objects.get(chore=chore)
    assert remaining.pk == existing_record.pk
    assert remaining.completed_by_id == first_completer.pk


@pytest.mark.django_db
def test_completed_chore_drops_out_of_personal_chores(client):
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = _make_chore(owner, title="Dishes")
    _log_in_as(client, owner)

    response = client.post(reverse("complete_chore", args=[chore.pk]))
    assert response.status_code == 302

    personal_response = client.get(reverse("personal_chores"))
    assert "Dishes" not in personal_response.content.decode()


@pytest.mark.django_db
def test_completed_chore_drops_out_of_family_overview(client):
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    completer = FamilyMember.objects.create(name="Eli", is_admin=False)
    chore = _make_chore(owner, title="Dishes")
    _log_in_as(client, completer)

    response = client.post(reverse("complete_chore", args=[chore.pk]))
    assert response.status_code == 302

    overview_response = client.get(reverse("family_overview"))
    assert "Dishes" not in overview_response.content.decode()


# --- #15: recurring chore next-occurrence generation ---


@pytest.mark.django_db
@pytest.mark.parametrize(
    "recurrence",
    [Chore.Recurrence.DAILY, Chore.Recurrence.WEEKLY, Chore.Recurrence.MONTHLY],
)
def test_completing_recurring_chore_generates_one_next_occurrence(client, recurrence):
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = _make_chore(
        owner,
        title="Vacuum",
        chore_type=Chore.ChoreType.RECURRING,
        recurrence=recurrence,
        priority=Chore.Priority.IMPORTANT,
    )
    _log_in_as(client, owner)

    response = client.post(reverse("complete_chore", args=[chore.pk]))

    assert response.status_code == 302
    next_occurrences = Chore.objects.exclude(pk=chore.pk)
    assert next_occurrences.count() == 1
    next_chore = next_occurrences.get()
    assert next_chore.title == chore.title
    assert next_chore.owner_id == chore.owner_id
    assert next_chore.priority == chore.priority
    assert next_chore.chore_type == Chore.ChoreType.RECURRING
    assert next_chore.recurrence == recurrence
    assert next_chore.is_active is True


@pytest.mark.django_db
def test_generating_next_occurrence_does_not_touch_original_completion_record(client):
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = _make_chore(
        owner,
        title="Vacuum",
        chore_type=Chore.ChoreType.RECURRING,
        recurrence=Chore.Recurrence.DAILY,
    )
    _log_in_as(client, owner)

    client.post(reverse("complete_chore", args=[chore.pk]))

    assert CompletionRecord.objects.filter(chore=chore).count() == 1
    next_chore = Chore.objects.exclude(pk=chore.pk).get()
    assert not CompletionRecord.objects.filter(chore=next_chore).exists()


@pytest.mark.django_db
def test_completing_one_time_chore_generates_nothing(client):
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = _make_chore(owner, title="Dishes", chore_type=Chore.ChoreType.ONE_TIME)
    _log_in_as(client, owner)

    response = client.post(reverse("complete_chore", args=[chore.pk]))

    assert response.status_code == 302
    assert Chore.objects.count() == 1


@pytest.mark.django_db
def test_reposting_complete_on_already_completed_recurring_chore_generates_no_extra_rows(
    client,
):
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = _make_chore(
        owner,
        title="Vacuum",
        chore_type=Chore.ChoreType.RECURRING,
        recurrence=Chore.Recurrence.WEEKLY,
    )
    _log_in_as(client, owner)

    first_response = client.post(reverse("complete_chore", args=[chore.pk]))
    assert first_response.status_code == 302
    assert Chore.objects.count() == 2

    second_response = client.post(reverse("complete_chore", args=[chore.pk]))
    assert second_response.status_code == 302
    assert Chore.objects.count() == 2
    assert CompletionRecord.objects.filter(chore=chore).count() == 1


@pytest.mark.django_db
def test_deactivating_completed_row_does_not_affect_generated_next_occurrence(client):
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    admin = FamilyMember.objects.create(name="Pat", is_admin=True)
    chore = _make_chore(
        owner,
        title="Vacuum",
        chore_type=Chore.ChoreType.RECURRING,
        recurrence=Chore.Recurrence.MONTHLY,
    )
    _log_in_as(client, owner)
    client.post(reverse("complete_chore", args=[chore.pk]))
    next_chore = Chore.objects.exclude(pk=chore.pk).get()

    _log_in_as(client, admin)
    deactivate_response = client.post(
        reverse("deactivate_chore", args=[chore.pk])
    )
    assert deactivate_response.status_code == 302

    next_chore.refresh_from_db()
    assert next_chore.is_active is True
    chore.refresh_from_db()
    assert chore.is_active is False


@pytest.mark.django_db
def test_editing_generated_next_occurrence_does_not_touch_completed_row(client):
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    admin = FamilyMember.objects.create(name="Pat", is_admin=True)
    chore = _make_chore(
        owner,
        title="Vacuum",
        chore_type=Chore.ChoreType.RECURRING,
        recurrence=Chore.Recurrence.WEEKLY,
    )
    _log_in_as(client, owner)
    client.post(reverse("complete_chore", args=[chore.pk]))
    next_chore = Chore.objects.exclude(pk=chore.pk).get()
    original_completion_record = CompletionRecord.objects.get(chore=chore)

    _log_in_as(client, admin)
    edit_response = client.post(
        reverse("edit_chore", args=[next_chore.pk]),
        {
            "title": "Vacuum living room",
            "owner": owner.pk,
            "priority": Chore.Priority.IMPORTANT,
            "recurrence": Chore.Recurrence.WEEKLY,
        },
    )
    assert edit_response.status_code == 302

    chore.refresh_from_db()
    assert chore.title == "Vacuum"
    assert chore.priority == Chore.Priority.NORMAL

    unchanged_record = CompletionRecord.objects.get(chore=chore)
    assert unchanged_record.pk == original_completion_record.pk
    assert unchanged_record.completed_at == original_completion_record.completed_at
