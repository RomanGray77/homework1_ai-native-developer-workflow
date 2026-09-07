"""Guardrail test for #17 (Due reminders).

#17 determined that the "due reminder" requirement (plan.md story 13) is
already satisfied by #11's personal_chores view: its Today/Overdue grouping
and Important-priority styling. No new Reminder model, notification channel,
or scheduled job is introduced by this issue - this file is a permanent
automated guardrail so a future change can't silently add a Reminder model
or break the section headings that stand in for reminders.

This intentionally does not re-derive #11's own grouping/styling tests
(tests/test_personal_chores.py::test_chores_grouped_into_correct_buckets and
::test_important_chore_marked_distinctly_in_html already cover that in
depth) - it only checks the two things #17 cares about.
"""

import datetime

import pytest
from django.urls import reverse

import chores.models
from chores.models import Chore, FamilyMember


def _log_in_as(client, member):
    session = client.session
    session["family_member_id"] = member.pk
    session.save()


def test_no_reminder_model_exists():
    # Locks in plan.md's Final MVP Boundary: no dedicated Reminder model,
    # table, or notification mechanism was added for this issue.
    assert not hasattr(chores.models, "Reminder")


@pytest.mark.django_db
def test_overdue_and_today_headings_render_with_their_chores(client):
    member = FamilyMember.objects.create(name="Dana", is_admin=False)
    today = datetime.date.today()
    overdue_chore = Chore.objects.create(
        title="Overdue chore",
        owner=member,
        chore_type=Chore.ChoreType.ONE_TIME,
        due_date=today - datetime.timedelta(days=1),
    )
    today_chore = Chore.objects.create(
        title="Today chore",
        owner=member,
        chore_type=Chore.ChoreType.ONE_TIME,
        due_date=today,
    )
    _log_in_as(client, member)

    response = client.get(reverse("personal_chores"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "<h2>Overdue</h2>" in content
    assert "<h2>Today</h2>" in content

    overdue_heading_index = content.index("<h2>Overdue</h2>")
    today_heading_index = content.index("<h2>Today</h2>")
    overdue_chore_index = content.index("Overdue chore")
    today_chore_index = content.index("Today chore")

    # Each chore is rendered under its own heading, not just present
    # somewhere in the page.
    assert overdue_heading_index < overdue_chore_index < today_heading_index
    assert today_heading_index < today_chore_index
