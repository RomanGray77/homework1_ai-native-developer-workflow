"""Tests for chores.views.personal_chores (#11).

No admin_required gate here - any selected family member may view their own
chores - but the session-check handling (missing/malformed/stale ->
redirect to select_member) mirrors admin_required's pattern (#6), so those
tests parallel tests/test_admin_required.py's. The "open chore" definition
(Chore.objects.active() (#10) plus no CompletionRecord) and the four
due_date-based grouping buckets (Overdue/Today/Upcoming/Later-no-due-date)
are #11's own acceptance criteria. This file also covers the follow-through
from #7 and #10: POST_SELECT_REDIRECT_URL_NAME and
POST_DEACTIVATE_REDIRECT_URL_NAME must now actually redirect here.
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


def _today():
    return datetime.date.today()


@pytest.mark.django_db
def test_personal_chores_url_name_resolves():
    assert reverse("personal_chores") == "/chores/"


@pytest.mark.django_db
def test_no_session_redirects_to_select_member(client):
    response = client.get(reverse("personal_chores"))

    assert response.status_code == 302
    assert response.url == reverse("select_member")


@pytest.mark.django_db
def test_malformed_session_value_redirects_not_500(client):
    session = client.session
    session["family_member_id"] = "not-an-int"
    session.save()

    response = client.get(reverse("personal_chores"))

    assert response.status_code == 302
    assert response.url == reverse("select_member")


@pytest.mark.django_db
def test_stale_nonexistent_session_id_redirects_not_500(client):
    session = client.session
    session["family_member_id"] = 999999
    session.save()

    response = client.get(reverse("personal_chores"))

    assert response.status_code == 302
    assert response.url == reverse("select_member")


@pytest.mark.django_db
def test_empty_state_when_no_open_chores(client):
    member = FamilyMember.objects.create(name="Dana", is_admin=False)
    _log_in_as(client, member)

    response = client.get(reverse("personal_chores"))

    assert response.status_code == 200
    assert "no open chores" in response.content.decode().lower()


@pytest.mark.django_db
def test_non_admin_member_can_view_own_chores(client):
    # No admin_required gate: a non-admin member can reach this view.
    member = FamilyMember.objects.create(name="Dana", is_admin=False)
    _make_chore(member, title="Dishes")
    _log_in_as(client, member)

    response = client.get(reverse("personal_chores"))

    assert response.status_code == 200
    assert "Dishes" in response.content.decode()


@pytest.mark.django_db
def test_chores_grouped_into_correct_buckets(client):
    member = FamilyMember.objects.create(name="Dana", is_admin=False)
    today = _today()
    overdue = _make_chore(
        member, title="Overdue chore", due_date=today - datetime.timedelta(days=1)
    )
    due_today = _make_chore(member, title="Today chore", due_date=today)
    upcoming = _make_chore(
        member, title="Upcoming chore", due_date=today + datetime.timedelta(days=1)
    )
    no_due_date = _make_chore(member, title="Someday chore", due_date=None)
    recurring = _make_chore(
        member,
        title="Recurring chore",
        chore_type=Chore.ChoreType.RECURRING,
        recurrence=Chore.Recurrence.WEEKLY,
        due_date=None,
    )
    _log_in_as(client, member)

    response = client.get(reverse("personal_chores"))

    assert response.status_code == 200
    assert list(response.context["overdue"]) == [overdue]
    assert list(response.context["due_today"]) == [due_today]
    assert list(response.context["upcoming"]) == [upcoming]
    assert set(response.context["later_or_no_due_date"]) == {no_due_date, recurring}


@pytest.mark.django_db
def test_buckets_ordered_by_due_date_then_title(client):
    member = FamilyMember.objects.create(name="Dana", is_admin=False)
    today = _today()
    later_overdue = _make_chore(
        member, title="B chore", due_date=today - datetime.timedelta(days=1)
    )
    earlier_overdue = _make_chore(
        member, title="A chore", due_date=today - datetime.timedelta(days=5)
    )
    same_day_b = _make_chore(
        member, title="B upcoming", due_date=today + datetime.timedelta(days=3)
    )
    same_day_a = _make_chore(
        member, title="A upcoming", due_date=today + datetime.timedelta(days=3)
    )
    later_z = _make_chore(member, title="Z someday", due_date=None)
    later_a = _make_chore(member, title="A someday", due_date=None)
    _log_in_as(client, member)

    response = client.get(reverse("personal_chores"))

    assert list(response.context["overdue"]) == [earlier_overdue, later_overdue]
    assert list(response.context["upcoming"]) == [same_day_a, same_day_b]
    assert list(response.context["later_or_no_due_date"]) == [later_a, later_z]


@pytest.mark.django_db
def test_completed_chore_excluded(client):
    member = FamilyMember.objects.create(name="Dana", is_admin=False)
    completed = _make_chore(member, title="Completed chore")
    CompletionRecord.objects.create(chore=completed, completed_by=member)
    open_chore = _make_chore(member, title="Open chore")
    _log_in_as(client, member)

    response = client.get(reverse("personal_chores"))

    later = list(response.context["later_or_no_due_date"])
    assert open_chore in later
    assert completed not in later


@pytest.mark.django_db
def test_inactive_chore_excluded(client):
    member = FamilyMember.objects.create(name="Dana", is_admin=False)
    inactive = _make_chore(member, title="Inactive chore", is_active=False)
    active = _make_chore(member, title="Active chore")
    _log_in_as(client, member)

    response = client.get(reverse("personal_chores"))

    later = list(response.context["later_or_no_due_date"])
    assert active in later
    assert inactive not in later


@pytest.mark.django_db
def test_another_members_chore_excluded(client):
    member = FamilyMember.objects.create(name="Dana", is_admin=False)
    other = FamilyMember.objects.create(name="Eli", is_admin=False)
    own_chore = _make_chore(member, title="My chore")
    other_chore = _make_chore(other, title="Not mine")
    _log_in_as(client, member)

    response = client.get(reverse("personal_chores"))

    later = list(response.context["later_or_no_due_date"])
    assert own_chore in later
    assert other_chore not in later


@pytest.mark.django_db
def test_important_chore_marked_distinctly_in_html(client):
    member = FamilyMember.objects.create(name="Dana", is_admin=False)
    _make_chore(
        member, title="Important chore", priority=Chore.Priority.IMPORTANT
    )
    _make_chore(member, title="Normal chore", priority=Chore.Priority.NORMAL)
    _log_in_as(client, member)

    response = client.get(reverse("personal_chores"))
    content = response.content.decode()

    # The important chore's markup must differ from the normal one's - e.g.
    # a distinguishing class or label - not just relying on implicit order.
    important_index = content.index("Important chore")
    normal_index = content.index("Normal chore")
    important_block_start = content.rfind("<li", 0, important_index)
    normal_block_start = content.rfind("<li", 0, normal_index)
    important_block_end = content.index("</li>", important_index)
    normal_block_end = content.index("</li>", normal_index)
    important_block = content[important_block_start:important_block_end]
    normal_block = content[normal_block_start:normal_block_end]

    assert "important" in important_block.lower()
    assert "important" not in normal_block.lower()


@pytest.mark.django_db
def test_post_select_member_redirect_lands_on_personal_chores(client):
    # End-to-end confirmation that POST_SELECT_REDIRECT_URL_NAME (#7 /
    # chores/views.py) was repointed from "health" to "personal_chores".
    member = FamilyMember.objects.create(name="Dana", is_admin=False)

    response = client.post(
        reverse("select_member"), {"family_member_id": member.pk}
    )

    assert response.status_code == 302
    assert response.url == reverse("personal_chores")

    followed = client.get(response.url)
    assert followed.status_code == 200


@pytest.mark.django_db
def test_post_deactivate_chore_redirect_lands_on_personal_chores(client):
    # End-to-end confirmation that POST_DEACTIVATE_REDIRECT_URL_NAME (#10 /
    # chores/views.py) was repointed from "health" to "personal_chores".
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = _make_chore(owner)
    _log_in_as(client, admin)

    response = client.post(reverse("deactivate_chore", args=[chore.pk]))

    assert response.status_code == 302
    assert response.url == reverse("personal_chores")

    followed = client.get(response.url)
    assert followed.status_code == 200
