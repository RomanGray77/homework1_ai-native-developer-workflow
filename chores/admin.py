from django.contrib import admin

from .models import Chore, CompletionRecord, FamilyMember


@admin.register(FamilyMember)
class FamilyMemberAdmin(admin.ModelAdmin):
    list_display = ("name", "is_admin")


@admin.register(Chore)
class ChoreAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "owner",
        "chore_type",
        "priority",
        "due_date",
        "recurrence",
        "is_active",
    )


@admin.register(CompletionRecord)
class CompletionRecordAdmin(admin.ModelAdmin):
    list_display = ("chore", "completed_by", "completed_at")
