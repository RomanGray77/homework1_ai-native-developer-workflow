from django.db import models
from django.utils import timezone


class FamilyMember(models.Model):
    name = models.CharField(max_length=150, unique=True, blank=False)
    is_admin = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class ChoreQuerySet(models.QuerySet):
    def active(self):
        """Chores that have not been deactivated (#10).

        Backing queryset for `Chore.objects.active()`. #11 (personal view)
        and #12 (family view) are expected to build their "open chore"
        filters on top of this once they land, per the breadcrumb comments
        left on those issues - this only guarantees the `is_active` half.
        """
        return self.filter(is_active=True)


class Chore(models.Model):
    class Priority(models.TextChoices):
        NORMAL = "normal", "Normal"
        IMPORTANT = "important", "Important"

    class ChoreType(models.TextChoices):
        ONE_TIME = "one_time", "One-time"
        RECURRING = "recurring", "Recurring"

    class Recurrence(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"

    title = models.CharField(max_length=200, blank=False)
    owner = models.ForeignKey(
        FamilyMember, on_delete=models.PROTECT, related_name="chores"
    )
    priority = models.CharField(
        max_length=20, choices=Priority.choices, default=Priority.NORMAL
    )
    chore_type = models.CharField(max_length=20, choices=ChoreType.choices)
    due_date = models.DateField(null=True, blank=True)
    recurrence = models.CharField(
        max_length=20, choices=Recurrence.choices, null=True, blank=True
    )
    is_active = models.BooleanField(default=True)

    objects = ChoreQuerySet.as_manager()

    def __str__(self):
        return self.title


class CompletionRecord(models.Model):
    chore = models.ForeignKey(
        Chore, on_delete=models.PROTECT, related_name="completion_records"
    )
    completed_by = models.ForeignKey(
        FamilyMember, on_delete=models.PROTECT, related_name="completion_records"
    )
    completed_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.chore} completed by {self.completed_by} at {self.completed_at}"
