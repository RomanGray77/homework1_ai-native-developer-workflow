from django.urls import path

from . import views

urlpatterns = [
    path("", views.health, name="health"),
    path("select/", views.select_member, name="select_member"),
    path("create/", views.create_chore, name="create_chore"),
    path("edit/<int:pk>/", views.edit_chore, name="edit_chore"),
    path("deactivate/<int:pk>/", views.deactivate_chore, name="deactivate_chore"),
    path("complete/<int:pk>/", views.complete_chore, name="complete_chore"),
    path("chores/", views.personal_chores, name="personal_chores"),
    path("family/", views.family_overview, name="family_overview"),
    path("chores/completed/", views.completed_chores, name="completed_chores"),
    path(
        "completion/<int:pk>/edit/",
        views.edit_completion_record,
        name="edit_completion_record",
    ),
    path(
        "completion/<int:pk>/delete/",
        views.delete_completion_record,
        name="delete_completion_record",
    ),
]
