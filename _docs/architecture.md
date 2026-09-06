# Architecture

This documents the technical architecture chosen for the Shared Household Chores MVP (see `plan.md` for product scope). The plan explicitly left backend/frontend architecture unspecified; this file is where that choice is made and recorded.

## Tech stack

- **Language / framework:** Python 3.13, Django 6.1 (MTV pattern, built-in ORM, built-in admin site).
- **Database:** SQLite (`db.sqlite3`). Sufficient for a single shared household instance with no concurrent-write scale concerns; no external DB server required.
- **Frontend:** Django server-rendered templates (`django.template`). No SPA framework or separate frontend build — matches the plan's "no prescribed frontend architecture" boundary and keeps the MVP simple.
- **Dependency management:** [`uv`](https://docs.astral.sh/uv/) — dependencies declared in `pyproject.toml`, resolved and pinned in `uv.lock`, virtual environment at `.venv/` managed by `uv sync`/`uv add`/`uv run` (no manual `venv`/`pip` steps).
- **Auth:** No login system. "Family member" is a data record the app lets a user pick from (see Domain layer below), not a Django `User`/session-authenticated account. Django's built-in admin (`django.contrib.admin`) is the only place real authentication is used, for admin-only actions.

## Project layout

```
manage.py                  # Django management entrypoint
household_chores/          # project package — global config, not domain logic
  settings.py
  urls.py                  # root URLConf, includes chores.urls
  wsgi.py / asgi.py
chores/                     # single Django app holding all domain logic
  models.py                # FamilyMember, Chore, CompletionRecord
  views.py                 # personal view, family view, completion actions
  urls.py                  # app-level routes, included from the project URLConf
  admin.py                 # admin-only create/edit/delete for chores & records
  migrations/
pyproject.toml             # project metadata + dependencies (uv)
uv.lock                    # locked dependency versions (uv)
db.sqlite3                 # local dev database (gitignored)
```

One app (`chores`) is used rather than splitting by feature, because the domain is small (family members, chores, completion records) and a single app keeps model relationships and migrations simple for an MVP.

## Request flow

Browser → `household_chores/urls.py` → `chores/urls.py` → view function/class in `chores/views.py` → Django ORM (`chores/models.py`) → SQLite → HTML template response. No API layer or JS client is introduced; every interaction (selecting a family member, viewing chores, completing a chore) is a normal Django view + template round trip.

## Domain layer (`chores` app)

Mapped from the user stories and decisions in `plan.md`:

- **FamilyMember** — `name`, `is_admin`. Stands in for an account; selecting one (story 1) is stored in the session, not via Django auth login.
- **Chore** — `title`, `owner` (FK → FamilyMember, fixed), `priority` (Normal/Important), `chore_type` (one-time/recurring), `due_date` (nullable, one-time only), `recurrence` (daily/weekly/monthly, recurring only), `is_active` (supports "delete stops future occurrences" without erasing history — Decision 3).
- **CompletionRecord** — `chore` (FK), `completed_by` (FK → FamilyMember), `completed_at`. One record per completed occurrence; deleting the record for a one-time chore reopens it (story 12). Recurring chores generate a new open occurrence after each completion rather than mutating the `Chore` row (Decision 2: edits to a recurring chore only affect future occurrences).
- Grouping (Today / Upcoming / Later–No due date / Overdue, Decision 1 & 4) and reminder generation (story 13) are computed in views/services from `due_date` and `recurrence`, not stored as separate state.

## Why this shape

- Single app + server-rendered templates avoids introducing an API contract, JS build step, or auth system the plan explicitly excludes (no separate logins, no prescribed architecture).
- SQLite avoids infra setup for a one-household app while still giving the "persistent storage" requirement (story 14) via standard Django migrations.
- Keeping "who is completing this" as a selectable `FamilyMember` rather than a Django `User` matches story 1's "no individual authentication" requirement while still letting `django.contrib.admin` use real auth for the separate admin-only operations (create/edit/delete chores, correct completion records).
