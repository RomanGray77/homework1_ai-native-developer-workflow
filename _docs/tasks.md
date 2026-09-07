# Backlog

Tasks for the Shared Household Chores MVP. Product scope and acceptance criteria are in `plan.md`; the chosen tech stack and data model are in `architecture.md`. Each task below is self-contained — it names the models/fields/views it touches so it can be picked up without reading the other tasks.

---

## 1. Project scaffolding with a passing test
Goal: A runnable Django project with one green test.
Description: Set up the `uv`-managed Django project (`household_chores` project, `chores` app), wired into `INSTALLED_APPS`. Add one trivial test (e.g. asserting the Django test client gets a 200 from a health-check or default URL) and confirm `uv run python manage.py test` passes.

## 2. FamilyMember model
Goal: Persist family member profiles.
Description: Add a `FamilyMember` model to `chores/models.py` with `name` and `is_admin` fields, register it in `chores/admin.py`, and generate/apply the migration. No views or permission logic yet — this task only covers the data layer.

## 3. Chore model
Goal: Persist chores with fixed ownership.
Description: Add a `Chore` model with `title`, `owner` (FK to `FamilyMember`), `priority` (Normal/Important), `chore_type` (one-time/recurring), `due_date` (nullable, one-time only), `recurrence` (daily/weekly/monthly, recurring only), and `is_active` (so deleting can stop future occurrences without erasing history). Register it in the admin and generate/apply the migration.

## 4. CompletionRecord model
Goal: Persist who completed a chore and when.
Description: Add a `CompletionRecord` model with `chore` (FK to `Chore`), `completed_by` (FK to `FamilyMember`), and `completed_at`. Register it in the admin and generate/apply the migration.

## 5. Persistence integration test
Goal: Prove data survives beyond a single request/process.
Description: Write a test that creates a `FamilyMember`, a `Chore`, and a `CompletionRecord`, then re-fetches each from the database (not from the objects still held in memory) to confirm the data round-trips correctly. This directly verifies the "persistent storage" acceptance criteria in `plan.md`.

## 6. Admin-only access control
Goal: A reusable way to restrict actions to admins.
Description: Add a small helper (e.g. a view decorator or mixin) that checks whether the currently selected `FamilyMember` has `is_admin = True`, and denies access otherwise. This will be reused by every admin-only view (create/edit/delete chore, correct completion records) so it should not assume any specific view's shape.

## 7. Family member selection ("who am I")
Goal: Let a user pick which family member they are, without login.
Description: Build a view where a user picks a `FamilyMember` from a list and the choice is stored in the session (no passwords, no Django auth `User`). Add a simple template listing all family members as the selection screen.

## 8. Create a chore
Goal: Let an admin create one-time or recurring chores.
Description: Build an admin-only (see task 6) form/view for creating a `Chore`, covering both one-time (optional `due_date`) and recurring (`recurrence` required) variants. Validate that recurring chores require a recurrence value and one-time chores don't.

## 9. Edit a chore
Goal: Let an admin correct a chore's details.
Description: Build an admin-only form/view to edit an existing `Chore`'s title, owner, priority, due date, and recurrence settings. Editing a recurring chore must only affect its future behavior — it must not rewrite any existing `CompletionRecord` history.

## 10. Delete (deactivate) a chore
Goal: Let an admin remove a chore without losing history.
Description: Build an admin-only action that sets a `Chore`'s `is_active` to `False` instead of deleting the row. For a one-time chore this removes it from the open list; for a recurring chore this stops future occurrences while existing `CompletionRecord`s remain untouched.

## 11. Personal chore view
Goal: Show one family member their own open chores.
Description: Build a view, scoped to the family member selected in task 7, listing only `Chore`s they own with `is_active=True` and no completion yet. Group results into Today / Upcoming / Later–No due date / Overdue sections based on `due_date`, and visually distinguish Important from Normal priority.

## 12. Family overview view
Goal: Show every open chore across the household.
Description: Build a view listing all active, uncompleted chores for every family member, showing each chore's owner. Use the same Today / Upcoming / Later–No due date / Overdue grouping as the personal view (task 11).

## 13. Complete a chore
Goal: Let any family member mark any chore done.
Description: Build an action (usable by any selected family member, not just the owner) that creates a `CompletionRecord` for a chore with `completed_by` set to the current family member and `completed_at` set to now. Once completed, the chore must no longer appear in the open lists from tasks 11/12.

## 14. Completed chores section
Goal: Show what's already been done.
Description: Build a view listing `CompletionRecord`s separately from open chores, showing chore title, assigned owner, who completed it, and when. This is a read-only view — no editing here (see task 16 for corrections).

## 15. Recurring chore next-occurrence generation
Goal: Keep recurring chores coming back after completion.
Description: When a recurring `Chore` is completed (task 13), generate the next open occurrence according to its `recurrence` schedule (daily/weekly/monthly) so the chore reappears in the open lists. Decide and document how an "occurrence" is represented (e.g. a computed next-due date on the same `Chore` row vs. a separate occurrence record).

## 16. Admin correction of completion records
Goal: Let an admin fix completion mistakes.
Description: Build an admin-only view to edit who completed a chore or when, or to delete a `CompletionRecord` entirely. Deleting the completion record for a one-time chore must make it open again; correcting a recurring occurrence's record must not affect its future recurrence schedule.

## 17. Due reminders
Goal: Notify an owner when their chore becomes due.
Description: Add a mechanism (e.g. a computed banner/list surfaced to the owner, not necessarily an email) that flags a dated `Chore` as needing attention once its `due_date` arrives, addressed to the chore's owner. No configurable timing and no repeated overdue notifications are required — one reminder signal per due chore is sufficient for the MVP.
