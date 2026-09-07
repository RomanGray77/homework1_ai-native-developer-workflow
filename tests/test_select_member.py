"""Tests for chores.views.select_member (#7).

The URL name "select_member" is a hard contract with #6's already-shipped
admin_required decorator (chores/decorators.py), which calls
redirect("select_member") whenever no family member is selected. These
tests guard that contract via reverse(), plus the rest of #7's acceptance
criteria: listing members, storing the selection in the session, redirecting
after a valid pick, the empty-household message, and handling a tampered
POST value without crashing.
"""

import pytest
from django.urls import reverse

from chores.models import FamilyMember


def test_select_member_url_name_resolves():
    # Guards the #6 redirect("select_member") contract: this must not raise
    # NoReverseMatch.
    assert reverse("select_member") == "/select/"


@pytest.mark.django_db
def test_get_lists_family_members_by_name(client):
    FamilyMember.objects.create(name="Alice", is_admin=True)
    FamilyMember.objects.create(name="Bob", is_admin=False)

    response = client.get(reverse("select_member"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Alice" in content
    assert "Bob" in content


@pytest.mark.django_db
def test_get_shows_message_when_no_members_exist(client):
    response = client.get(reverse("select_member"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "No family members yet" in content


@pytest.mark.django_db
def test_screen_never_shows_password_or_login_form(client):
    response = client.get(reverse("select_member"))

    content = response.content.decode().lower()
    assert "password" not in content
    assert "login" not in content


@pytest.mark.django_db
def test_post_valid_member_sets_session_and_redirects(client):
    member = FamilyMember.objects.create(name="Alice", is_admin=True)

    response = client.post(
        reverse("select_member"), {"family_member_id": member.pk}
    )

    assert response.status_code == 302
    assert client.session["family_member_id"] == member.pk


@pytest.mark.django_db
def test_post_valid_member_redirects_to_personal_chores(client):
    # #11's POST_SELECT_REDIRECT_URL_NAME follow-through: a successful
    # selection now lands on the personal chore view, not the "health"
    # placeholder used before #11 existed.
    member = FamilyMember.objects.create(name="Alice", is_admin=True)

    response = client.post(
        reverse("select_member"), {"family_member_id": member.pk}
    )

    assert response.status_code == 302
    assert response.url == reverse("personal_chores")


@pytest.mark.django_db
def test_post_invalid_member_id_rerenders_with_error_not_crash(client):
    FamilyMember.objects.create(name="Alice", is_admin=True)

    response = client.post(reverse("select_member"), {"family_member_id": 999999})

    assert response.status_code == 200
    assert "family_member_id" not in client.session
    content = response.content.decode()
    assert "not a valid family member" in content.lower() or "error" in content.lower()


@pytest.mark.django_db
def test_post_non_numeric_member_id_rerenders_with_error_not_crash(client):
    FamilyMember.objects.create(name="Alice", is_admin=True)

    response = client.post(
        reverse("select_member"), {"family_member_id": "not-an-int"}
    )

    assert response.status_code == 200
    assert "family_member_id" not in client.session


@pytest.mark.django_db
def test_select_member_reachable_even_with_member_already_selected(client):
    member = FamilyMember.objects.create(name="Alice", is_admin=True)
    session = client.session
    session["family_member_id"] = member.pk
    session.save()

    response = client.get(reverse("select_member"))

    assert response.status_code == 200
