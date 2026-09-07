"""Tests for chores.views.family_overview (#12).

No admin_required gate and no family-member-selection gate at all - unlike
personal_chores (#11), this view is not personalized to any one member, so
it must render identically whether family_member_id is absent, malformed,
stale, or a valid selection (admin or not). "Open chore" (Chore.objects.
active() (#10) plus no CompletionRecord) and the four due_date-based
grouping buckets (Overdue/Today/Upcoming/Later-no-due-date) mirror #11's
definitions exactly, but across every owner rather than scoped to a session
selection. This file also covers the follow-through from #8/#9:
POST_CREATE_REDIRECT_URL_NAME and POST_EDIT_REDIRECT_URL_NAME must now
actually redirect here.
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
def test_family_overview_url_name_resolves():
    assert reverse("family_overview") == "/family/"


@pytest.mark.django_db
def test_no_session_at_all_still_renders(client):
    member = FamilyMember.objects.create(name="Dana", is_admin=False)
    _make_chore(member, title="Dishes")

    response = client.get(reverse("family_overview"))

    assert response.status_code == 200
    assert "Dishes" in response.content.decode()


@pytest.mark.django_db
def test_malformed_session_value_still_renders(client):
    member = FamilyMember.objects.create(name="Dana", is_admin=False)
    _make_chore(member, title="Dishes")
    session = client.session
    session["family_member_id"] = "not-an-int"
    session.save()

    response = client.get(reverse("family_overview"))

    assert response.status_code == 200
    assert "Dishes" in response.content.decode()


@pytest.mark.django_db
def test_stale_nonexistent_session_id_still_renders(client):
    member = FamilyMember.objects.create(name="Dana", is_admin=False)
    _make_chore(member, title="Dishes")
    session = client.session
    session["family_member_id"] = 999999
    session.save()

    response = client.get(reverse("family_overview"))

    assert response.status_code == 200
    assert "Dishes" in response.content.decode()


@pytest.mark.django_db
def test_non_admin_selected_member_can_access(client):
    member = FamilyMember.objects.create(name="Dana", is_admin=False)
    _make_chore(member, title="Dishes")
    _log_in_as(client, member)

    response = client.get(reverse("family_overview"))

    assert response.status_code == 200
    assert "Dishes" in response.content.decode()


@pytest.mark.django_db
def test_admin_selected_member_can_access(client):
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    _make_chore(admin, title="Dishes")
    _log_in_as(client, admin)

    response = client.get(reverse("family_overview"))

    assert response.status_code == 200
    assert "Dishes" in response.content.decode()


@pytest.mark.django_db
def test_empty_state_when_no_open_chores(client):
    response = client.get(reverse("family_overview"))

    assert response.status_code == 200
    assert "no open chores" in response.content.decode().lower()


@pytest.mark.django_db
def test_chores_from_multiple_owners_all_appear_with_owner_name(client):
    dana = FamilyMember.objects.create(name="Dana", is_admin=False)
    eli = FamilyMember.objects.create(name="Eli", is_admin=False)
    _make_chore(dana, title="Dana chore")
    _make_chore(eli, title="Eli chore")

    response = client.get(reverse("family_overview"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Dana chore" in content
    assert "Eli chore" in content
    assert "Dana" in content
    assert "Eli" in content


@pytest.mark.django_db
def test_chores_grouped_into_correct_buckets(client):
    dana = FamilyMember.objects.create(name="Dana", is_admin=False)
    eli = FamilyMember.objects.create(name="Eli", is_admin=False)
    today = _today()
    overdue = _make_chore(
        dana, title="Overdue chore", due_date=today - datetime.timedelta(days=1)
    )
    due_today = _make_chore(eli, title="Today chore", due_date=today)
    upcoming = _make_chore(
        dana, title="Upcoming chore", due_date=today + datetime.timedelta(days=1)
    )
    no_due_date = _make_chore(eli, title="Someday chore", due_date=None)
    recurring = _make_chore(
        dana,
        title="Recurring chore",
        chore_type=Chore.ChoreType.RECURRING,
        recurrence=Chore.Recurrence.WEEKLY,
        due_date=None,
    )

    response = client.get(reverse("family_overview"))

    assert response.status_code == 200
    assert list(response.context["overdue"]) == [overdue]
    assert list(response.context["due_today"]) == [due_today]
    assert list(response.context["upcoming"]) == [upcoming]
    assert set(response.context["later_or_no_due_date"]) == {no_due_date, recurring}


@pytest.mark.django_db
def test_buckets_ordered_by_due_date_then_title(client):
    dana = FamilyMember.objects.create(name="Dana", is_admin=False)
    today = _today()
    later_overdue = _make_chore(
        dana, title="B chore", due_date=today - datetime.timedelta(days=1)
    )
    earlier_overdue = _make_chore(
        dana, title="A chore", due_date=today - datetime.timedelta(days=5)
    )
    same_day_b = _make_chore(
        dana, title="B upcoming", due_date=today + datetime.timedelta(days=3)
    )
    same_day_a = _make_chore(
        dana, title="A upcoming", due_date=today + datetime.timedelta(days=3)
    )
    later_z = _make_chore(dana, title="Z someday", due_date=None)
    later_a = _make_chore(dana, title="A someday", due_date=None)

    response = client.get(reverse("family_overview"))

    assert list(response.context["overdue"]) == [earlier_overdue, later_overdue]
    assert list(response.context["upcoming"]) == [same_day_a, same_day_b]
    assert list(response.context["later_or_no_due_date"]) == [later_a, later_z]


@pytest.mark.django_db
def test_completed_chore_excluded(client):
    member = FamilyMember.objects.create(name="Dana", is_admin=False)
    completed = _make_chore(member, title="Completed chore")
    CompletionRecord.objects.create(chore=completed, completed_by=member)
    open_chore = _make_chore(member, title="Open chore")

    response = client.get(reverse("family_overview"))

    later = list(response.context["later_or_no_due_date"])
    assert open_chore in later
    assert completed not in later


@pytest.mark.django_db
def test_inactive_chore_excluded(client):
    member = FamilyMember.objects.create(name="Dana", is_admin=False)
    inactive = _make_chore(member, title="Inactive chore", is_active=False)
    active = _make_chore(member, title="Active chore")

    response = client.get(reverse("family_overview"))

    later = list(response.context["later_or_no_due_date"])
    assert active in later
    assert inactive not in later


@pytest.mark.django_db
def test_important_chore_marked_distinctly_in_html(client):
    member = FamilyMember.objects.create(name="Dana", is_admin=False)
    _make_chore(member, title="Important chore", priority=Chore.Priority.IMPORTANT)
    _make_chore(member, title="Normal chore", priority=Chore.Priority.NORMAL)

    response = client.get(reverse("family_overview"))
    content = response.content.decode()

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
def test_post_create_chore_redirect_lands_on_family_overview(client):
    # End-to-end confirmation that POST_CREATE_REDIRECT_URL_NAME (#8 /
    # chores/views.py) was repointed from "health" to "family_overview".
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    session = client.session
    session["family_member_id"] = admin.pk
    session.save()

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
    assert response.url == reverse("family_overview")

    followed = client.get(response.url)
    assert followed.status_code == 200
    assert "Mow the lawn" in followed.content.decode()


@pytest.mark.django_db
def test_post_edit_chore_redirect_lands_on_family_overview(client):
    # End-to-end confirmation that POST_EDIT_REDIRECT_URL_NAME (#9 /
    # chores/views.py) was repointed from "health" to "family_overview".
    admin = FamilyMember.objects.create(name="Alice", is_admin=True)
    owner = FamilyMember.objects.create(name="Dana", is_admin=False)
    chore = Chore.objects.create(
        title="Mow the lawn",
        owner=owner,
        chore_type=Chore.ChoreType.ONE_TIME,
    )
    session = client.session
    session["family_member_id"] = admin.pk
    session.save()

    response = client.post(
        reverse("edit_chore", args=[chore.pk]),
        {
            "title": "Mow the back lawn",
            "owner": owner.pk,
            "priority": Chore.Priority.NORMAL,
            "due_date": "",
            "recurrence": "",
        },
    )

    assert response.status_code == 302
    assert response.url == reverse("family_overview")

    followed = client.get(response.url)
    assert followed.status_code == 200
    assert "Mow the back lawn" in followed.content.decode()
