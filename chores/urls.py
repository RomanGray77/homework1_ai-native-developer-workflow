from django.urls import path

from . import views

urlpatterns = [
    path("", views.health, name="health"),
    path("select/", views.select_member, name="select_member"),
    path("create/", views.create_chore, name="create_chore"),
    path("edit/<int:pk>/", views.edit_chore, name="edit_chore"),
]
