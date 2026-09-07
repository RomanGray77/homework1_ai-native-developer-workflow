"""Tests for chores.decorators.admin_required.

The selection screen (#7) does not exist yet, but #6's contract pins the
redirect target to the URL name "select_member". To test the decorator in
isolation (per #6's acceptance criteria) without depending on #7, this file
defines its own throwaway view + a throwaway "select_member" stub view, and
swaps in a local URLconf (this module itself) for the duration of the tests
via the `settings` fixture. That gives `redirect("select_member")` something
real to resolve against, without requiring #7's actual screen/template.
"""

import pytest
from django.http import HttpResponse
from django.urls import path

from chores.decorators import admin_required
from chores.models import FamilyMember


@admin_required
def throwaway_admin_view(request):
    return HttpResponse("secret admin content")


def throwaway_select_member_view(request):
    return HttpResponse("pick a family member")


urlpatterns = [
    path("throwaway-admin/", throwaway_admin_view, name="throwaway_admin"),
    path(
        "throwaway-select-member/",
        throwaway_select_member_view,
        name="select_member",
    ),
]


@pytest.fixture(autouse=True)
def _local_urlconf(settings):
    # Point ROOT_URLCONF at this test module so "select_member" resolves,
    # without touching the real chores/urls.py (which #7 will own).
    settings.ROOT_URLCONF = __name__


@pytest.mark.django_db
def test_no_session_redirects_to_select_member(client):
    response = client.get("/throwaway-admin/")

    assert response.status_code == 302
    assert response.url == "/throwaway-select-member/"


@pytest.mark.django_db
def test_malformed_session_value_redirects_not_500(client):
    session = client.session
    session["family_member_id"] = "not-an-int"
    session.save()

    response = client.get("/throwaway-admin/")

    assert response.status_code == 302
    assert response.url == "/throwaway-select-member/"


@pytest.mark.django_db
def test_stale_nonexistent_id_redirects_not_500(client):
    session = client.session
    session["family_member_id"] = 999999
    session.save()

    response = client.get("/throwaway-admin/")

    assert response.status_code == 302
    assert response.url == "/throwaway-select-member/"


@pytest.mark.django_db
def test_non_admin_gets_403(client):
    member = FamilyMember.objects.create(name="Bob", is_admin=False)
    session = client.session
    session["family_member_id"] = member.pk
    session.save()

    response = client.get("/throwaway-admin/")

    assert response.status_code == 403


@pytest.mark.django_db
def test_admin_view_executes_normally(client):
    member = FamilyMember.objects.create(name="Alice", is_admin=True)
    session = client.session
    session["family_member_id"] = member.pk
    session.save()

    response = client.get("/throwaway-admin/")

    assert response.status_code == 200
    assert response.content == b"secret admin content"
