from django.db import models


class FamilyMember(models.Model):
    name = models.CharField(max_length=150, unique=True, blank=False)
    is_admin = models.BooleanField(default=False)

    def __str__(self):
        return self.name


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

    def __str__(self):
        return self.title
