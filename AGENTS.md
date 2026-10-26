# AGENTS.md — STARTR-django-code

Rules for agents working in this repo. What the starter is, install and usage: [README.md](README.md). Open work: [TODO.md](TODO.md).

## What it is

Django Startr generates CRUD from Django models: views, forms, URLs, admin and templates, with `python manage.py startr <app>`. It also ships the admin skin, the nav (dock, tiers, user menu) and the delete confirmation. Everything is in `django_startr/`.

## Install order

A consumer lists the admin skin before the admin and the package after it:

```python
INSTALLED_APPS = [
    "django_startr.admin_skin",   # before the admin: its admin/base_site.html and admin/login.html must win
    "django.contrib.admin",
    # ...
    "django_startr",              # after it: its registration/*.html must not shadow the admin's
]
```

Put `django_startr` ahead of the admin and its `registration/*.html` shadow the admin's. Log out then returns a 500.

- `startr.W001`: the skin's `admin/base_site.html` is not the one served, so Django's sidebar stays (`django_startr/admin_skin/checks.py`).
- `startr.W002`: the engine that renders the admin lacks the `request` context processor, so no tier can mark the current page.
- Run `manage.py check` after any change to `INSTALLED_APPS` or `TEMPLATES`.

## Settings

All are optional; the README tables are the reference. The families:

- Nav: `STARTR_NAV_ORDER`, `_HIDE`, `_LABEL`, `_EXTRA`, `_ANON`, `_PRIMARY`, `_DOCK`, `_GROUPS`, `_ICONS`, `_MENU` (the user menu's back-office pages).
- Admin: `STARTR_ADMIN_TITLE`, `STARTR_ADMIN_NAV`, `STARTR_ADMIN_SMART_SELECT`.
- Pages: `STARTR_BASE_TEMPLATE`, `STARTR_DELETE_CONFIRM`, `STARTR_DELETE_BUTTON_STYLE`, `STARTR_READONLY_MODELS`, `STARTR_STYLE_URL`.

## Tests

The suite runs inside a consumer's container, because it needs that project's Django. From the Trellis checkout:

```bash
docker exec -e DJANGO_SETTINGS_MODULE= <trellis container> python -m unittest django_startr.tests
```

## How changes flow

Edit the starter in a consumer's subtree (Trellis: `our_subtrees/STARTR-django-code`), never in a standalone clone. `make startr_push` in that consumer sends the change to this repo's master. Other consumers bring it in with `make startr_pull`.

## Shared rules

The same block sits in every Sage.is and Startr repo's AGENTS.md; change it everywhere or nowhere.

- **Git.** Agents commit and push only when the person they work for says so in that session. Commits are authored as that person and carry an AI co-author trailer. Subjects read `type(scope): subject` (`feat`, `fix`, `docs`, `refactor`, `test`, `chore`).
- **Design.** startr.style inline props in `style` attributes, never classes. Write the base (phone) value first; add an `-sm`/`-md`/`-lg`/`-xl` tier only where the layout changes, and never repeat the base value in a tier. New pages ship plain HTML first; never a third visual language. The kit's manual is [design-ingest.md](https://github.com/Startr/WEB-startr.style.core/blob/master/docs/design-ingest.md).
- **Browser checks are scripts.** `bun run probe:hover`, `probe:tap` and `probe:diff` run from a WEB-startr.style.core checkout and take seconds; they replace long agent sessions clicking through pages.
- **Steps.** A step in a runbook, run sheet or checklist is one command: `cd` to an absolute path, then commands joined with `&&` and broken with `\`, so it stops at its first failure and can later run unchanged as a Dockerfile `RUN` or a CI step. A step calls a make target, not inline logic. No inline `#` comments (interactive zsh runs them as commands), no pasted `set -e`, no heredocs; a step that needs a key touch, a password or `git add -p` stays its own [MANUALLY] step.
- **Board.** `TODO.md` sections are the kanban columns. Each card is one short claim line (under about 350 characters) with a sub-checklist; narration goes to `board-dossiers.md` in the docs folder. `KANBAN.canvas` is generated from `TODO.md`; never hand-edit it.
- **Names.** Tracked files name work paths, not people; only Alexander is named. Clients go by codename.
- **Secrets.** In the environment or the team vault; never in chat, a command line or a tracked file.
