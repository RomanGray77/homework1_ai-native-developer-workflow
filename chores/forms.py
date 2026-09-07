from django import forms

from .models import Chore, FamilyMember


class CreateChoreForm(forms.Form):
    """Form backing the create-chore view (#8).

    `owner` uses ModelChoiceField so a tampered/nonexistent id is rejected
    with a normal validation error rather than a 500 (same handling style as
    #7's member selection). The one_time/recurring cross-field rules from
    `_docs/architecture.md` (due_date is one-time only, recurrence is
    recurring only) are enforced in `clean()` since they involve more than
    one field.
    """

    title = forms.CharField(max_length=200)
    owner = forms.ModelChoiceField(queryset=FamilyMember.objects.none())
    priority = forms.ChoiceField(
        choices=Chore.Priority.choices,
        required=False,
        initial=Chore.Priority.NORMAL,
    )
    chore_type = forms.ChoiceField(choices=Chore.ChoreType.choices)
    due_date = forms.DateField(required=False)
    recurrence = forms.ChoiceField(
        choices=Chore.Recurrence.choices, required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populated per-instantiation (not as a class-level default) so newly
        # created FamilyMember rows are picked up on every request.
        self.fields["owner"].queryset = FamilyMember.objects.order_by("name")

    def clean(self):
        cleaned_data = super().clean()
        chore_type = cleaned_data.get("chore_type")
        due_date = cleaned_data.get("due_date")
        recurrence = cleaned_data.get("recurrence")

        if chore_type == Chore.ChoreType.RECURRING:
            if not recurrence:
                self.add_error(
                    "recurrence",
                    "Recurring chores must have a recurrence set.",
                )
            if due_date:
                self.add_error(
                    "due_date",
                    "Recurring chores don't use a due date (one-time only).",
                )
        elif chore_type == Chore.ChoreType.ONE_TIME:
            if recurrence:
                self.add_error(
                    "recurrence",
                    "One-time chores must not have a recurrence set.",
                )

        return cleaned_data

    def save(self):
        """Create and return the Chore. Only call after is_valid() passes."""
        return Chore.objects.create(
            title=self.cleaned_data["title"],
            owner=self.cleaned_data["owner"],
            priority=self.cleaned_data.get("priority") or Chore.Priority.NORMAL,
            chore_type=self.cleaned_data["chore_type"],
            due_date=self.cleaned_data.get("due_date"),
            recurrence=self.cleaned_data.get("recurrence") or None,
        )
