from django.contrib import admin

from .models import FamilyMember


@admin.register(FamilyMember)
class FamilyMemberAdmin(admin.ModelAdmin):
    list_display = ("name", "is_admin")
