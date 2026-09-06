# Shared Household Chores — MVP

## Scope summary

A shared family web application where admins create fixed-owner one-time or recurring chores, everyone can see personal and family views, any family member can complete a chore, completion history is recorded, and owners receive simple due reminders.

The MVP deliberately excludes separate user accounts, statistics, gamification, custom recurrence rules, attachments, advanced notification settings, and architecture constraints.

---

# User Stories and Acceptance Criteria

## 1. Family members

### User story
As a family member, I want to select who I am so that I can see my chores without needing a separate login.

### Acceptance criteria
- The app has one shared family account.
- No individual authentication is required.
- A user can select a family member profile.
- The selected family member can see their personal chore view.
- All family members can also access the full family overview.

---

## 2. Create a chore

### User story
As an admin, I want to create a chore and assign it to a family member so that responsibility is clear.

### Acceptance criteria
- Only admins can create chores.
- A chore must have:
  - title
  - owner
  - priority: Normal or Important
  - type: one-time or recurring
- Chores do not contain descriptions, notes, or attachments.
- A chore always has one fixed owner.

---

## 3. Create a one-time chore

### User story
As an admin, I want to create a one-time chore so that occasional household tasks can be tracked.

### Acceptance criteria
- A one-time chore may have an optional due date.
- If no due date is provided, the chore remains open until completed.
- The chore appears in the family overview and in the owner's personal view.

---

## 4. Create a recurring chore

### User story
As an admin, I want to create a recurring chore so that regular household responsibilities are generated automatically.

### Acceptance criteria
- A recurring chore supports:
  - Daily
  - Weekly
  - Monthly
- The recurrence schedule is required.
- The chore keeps the same fixed owner.
- After one occurrence is completed, future occurrences remain scheduled.

---

## 5. Edit a chore

### User story
As an admin, I want to edit an existing chore so that assignments and schedules can be corrected.

### Acceptance criteria
- Only admins can edit chores.
- An admin can change:
  - title
  - owner
  - priority
  - due date
  - recurrence settings
- Editing a recurring chore affects future occurrences.

---

## 6. Delete a chore

### User story
As an admin, I want to delete a chore so that obsolete chores no longer appear.

### Acceptance criteria
- Only admins can delete chores.
- Deleting a one-time chore removes the open chore.
- Deleting a recurring chore stops future occurrences.
- Existing completion records are not automatically removed.

---

## 7. View personal chores

### User story
As a family member, I want to see the chores assigned to me so that I know what I am responsible for.

### Acceptance criteria
- A user can switch to a personal view.
- Only chores owned by the selected family member are shown.
- Open chores are organized by due date.
- Important chores are visually distinguishable from Normal chores.

---

## 8. View family chores

### User story
As a family member, I want to see all household chores so that I understand what needs to be done across the family.

### Acceptance criteria
- All family members can access the family overview.
- The overview includes chores belonging to every family member.
- Each chore shows its owner.
- Open chores are organized by due date.

---

## 9. Organize chores by due date

### User story
As a family member, I want chores grouped by when they are due so that I can quickly see what needs attention.

### Acceptance criteria
- Open chores are grouped into sections such as:
  - Today
  - Upcoming
  - Later / No due date
- Overdue chores are clearly identifiable.
- Completed chores are not mixed with open chores.

---

## 10. Complete a chore

### User story
As a family member, I want to mark a chore as completed so that the family knows it has been done.

### Acceptance criteria
- Any family member can complete any chore, even if they are not its owner.
- On completion, the app records:
  - the chore
  - who actually completed it
  - completion date and time
- The completed chore is removed from the open list.
- It appears in the Completed section.

---

## 11. View completed chores

### User story
As a family member, I want to see completed chores separately so that I can check what has already been done.

### Acceptance criteria
- The app contains a separate Completed section.
- Completed records show:
  - chore title
  - assigned owner
  - person who completed it
  - completion date and time
- Completed chores do not appear in the normal open-chore sections.

---

## 12. Correct completed records

### User story
As an admin, I want to correct or delete a completion record so that mistakes can be fixed.

### Acceptance criteria
- Only admins can modify completion records.
- An admin can correct who completed the chore or when it was completed.
- An admin can delete a completion record.
- If a completion record for a one-time chore is deleted, the chore becomes open again.
- If a recurring occurrence is corrected, future recurrence remains unchanged.

---

## 13. Reminder when a chore is due

### User story
As the owner of a chore, I want to receive a reminder when it becomes due so that I do not forget it.

### Acceptance criteria
- A reminder is generated when a dated chore becomes due.
- The reminder is addressed to the chore owner.
- No configurable reminder times are required.
- No repeated overdue notifications are required for the MVP.

---

## 14. Persistent storage

### User story
As a family, we want our chore information to be saved so that it is still available after closing the application.

### Acceptance criteria
- Family members are persisted.
- Chores are persisted.
- Recurrence information is persisted.
- Completion records are persisted.
- Restarting or reopening the application does not erase existing data.

---

# Product Decisions Added to Make the MVP Unambiguous

## Decision 1: Add an explicit Overdue state

Overdue chores should be shown separately or clearly marked as overdue.

### Why
Without this, a chore due yesterday does not fit cleanly into Today, Upcoming, or Later.

### Alternatives considered
- Put overdue chores inside Today.
- Leave them in chronological order without a special state.

### Decision
Use an explicit **Overdue** indication because it makes the interface easier to understand without adding meaningful complexity.

---

## Decision 2: Editing recurring chores changes future occurrences only

If an admin changes the owner or schedule of a recurring chore, existing completion history should stay unchanged.

### Why
Historical records should describe what actually happened at that time.

### Alternatives considered
- Retroactively update all historical records.
- Ask the admin whether to update past or future occurrences.

### Decision
Only future occurrences are changed. Asking the admin each time is more powerful but unnecessarily complex for the MVP.

---

## Decision 3: Deleting a recurring chore does not delete history

Stopping a recurring chore should stop future occurrences but preserve completed occurrences.

### Why
A completed record is historical information, not part of the active schedule.

### Alternative considered
- Delete the chore and all associated history.

### Decision
Preserve completion history because deleting it would be surprising from a user perspective.

---

## Decision 4: Undated one-time chores go into “No due date”

One-time chores without a due date should remain visible in a separate **No due date** group.

### Why
Otherwise they could disappear from a date-oriented interface.

### Alternatives considered
- Put them in Later.
- Require every one-time chore to have a due date.

### Decision
Use a separate **No due date** group because requiring a date would contradict the chosen MVP behavior.

---

## Decision 5: No statistics, points, fairness scoring, or gamification

The MVP should deliberately exclude:
- points
- streaks
- workload balancing
- statistics
- leaderboards
- automatic rotation

### Why
These features would turn a simple household task manager into a more complex chore-management system with significantly more business logic.

For this homework, the important domain concepts are already sufficient:
- family members
- chores
- ownership
- recurrence
- completion
- permissions
- reminders

---

# Final MVP Boundary

The MVP is a **simple responsive web application** for one family household.

It supports:
- one shared family app
- family member profile selection
- admins who can create and edit chores
- fixed chore ownership
- one-time chores
- daily, weekly, and monthly recurring chores
- optional due dates for one-time chores
- Normal and Important priority
- personal chore view
- full family overview
- due-date-based organization
- a separate Completed section
- any family member completing any chore
- recording who actually completed a chore and when
- admin correction or deletion of completion records
- simple due reminders
- persistent database storage

It does **not** include:
- separate user logins
- notes or attachments
- custom recurrence intervals
- configurable reminders
- overdue reminder sequences
- statistics
- leaderboards
- points
- gamification
- automatic chore rotation
- prescribed backend or frontend architecture
