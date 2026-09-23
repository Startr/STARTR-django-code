# Roadmap — django-startr

Generator for Django CRUD: views, forms, urls, admin and templates from models.
Migrating from DTL meta-templates to Jinja2. Plan and rationale in
`docs/decisions/`.

> **Convention** — Sections below map to kanban columns. Inline source-code
> tags use the same vocabulary so items stay cross-referenced between this
> file and the codebase. `KANBAN.canvas` auto-generates from this file and
> inline tags — do not hand-edit it.
>
> | Column      | Markdown section  | Inline tag  |
> |-------------|-------------------|-------------|
> | Backlog     | `## Backlog`      |             |
> | TODO        | `## TODO`         | `# TODO:`   |
> | In Progress | `## In Progress`  | `# FIXME:`  |
> | Bugs        | `## Bugs`         | `# BUG:`    |
> | Done        | `- [x]` items / `## Done` | —   |
>
> `# DEPRECATED:` tags should be tracked as TODO items for removal at the
> stated version.

## In Progress

- [ ] **Git setup** (Alexander — this session never writes to git)
  - [ ] `git checkout -b develop` from master
  - [ ] `git tag v0.22.0 master` — `make version_check` warns until it lands
  - [ ] Confirm this fork, not `opencoca/STARTR-WEB-OPS-django-startr`


## TODO

### Sprint 2 — search, guards, gold test

- [x] **Server-side search in the views emitter**: `?q=` across text fields
  - [x] `get_queryset` ANDs words, ORs fields, ends in `.distinct()`
  - [x] Field list from model introspection, text-ish concrete fields only
  - [x] Reuse the reastate pattern, do not write a second implementation
    <!-- inline: WEB-AI-Sage-Sprig-reastate/crm/services/leads.py -->

- [ ] **CLI flags on `manage.py startr`**
  - [ ] `--dry-run` prints the plan, writes nothing
  - [ ] `--quiet`
  - [ ] `--prune` guards `remove_empty_startapp_files`, default OFF
    <!-- inline: django_startr/startry.py:161 -->

- [ ] **Test suite**: 17 tests, all running under pipenv
  - [x] `form.as_p()` called not referenced; no `bound method` in output
  - [x] No stub carries `templatetag`, `verbatim`, or an interpreted attribute
  - [x] Every Python emitter renders to a module that `ast.parse` accepts
  - [x] `StrictUndefined` fires on a mistyped meta variable
  - [ ] Re-run leaves every hand-written file byte-identical
  - [ ] `--dry-run` leaves a directory checksum unchanged

- [ ] **Gold test against reastate**: generate the CRUD not yet hand-written
  - [x] All 5 generated pages render live, anon and authenticated — 10/10 green
  - [ ] Run the real `startr crm:Party,Thread,Task,PartialLead --dry-run`
  - [ ] Generate for real against the container
  - [ ] Confirm hand-written `crm/views/leads.py` untouched

### Sprint 3 — dev notes and model drift

- [ ] **Dev-notes tests**: the module exists, the proof does not
  - [x] `devnotes.py` — five callables, `DEBUG`-gated, no stylesheet
  - [ ] `DEBUG=False` renders zero bytes — the fail-closed gate
  - [ ] Markup carries no `style=` and no hex colour
  - [ ] `{% call todo() %}` paired form renders through a real backend

- [ ] **Regeneration manifest**: `<app>/.startr-manifest.json`
  - [ ] Record field set and a sha256 per generated file
  - [ ] Version the schema from day one

- [ ] **`--amend` under model drift**
  - [ ] Field added → insert a `devnote` naming it
  - [ ] Field removed → WARNING, edit nothing
  - [ ] Sha mismatch → hand-edited, never touched

### Sprint 4 — knowledge that travels with the clone

- [ ] **In-repo docs**
  - [x] `docs/decisions/2026-08-20-jinja2-meta-delimiters.md` — SPK1 output
  - [ ] `docs/JINJA2-MIGRATION.md` — conversion table, incl. the two rows SPK1 found
  - [ ] `AGENTS.md` — what an agent must never do here
  - [ ] `docs/PROMPTS.md` — worked prompts
  - [ ] `README.md` rewrite — install, wire `TEMPLATES`, run, flags

- [ ] **`/startr-django` skill**: sibling of `/startr-init`
  - [ ] Point at the in-repo docs rather than restating them
  - [ ] Cover the ui-Sprig grant nuance: script yes, hyperscript never

### Upstream

- [ ] **startr.style: base styling for `aside`** (Alexander — sign-off first)
  - [ ] `src/base/_aside.css`, `@import` from `builds/startr-base.css`
  - [ ] Inset and bordered from `--border` / `--text-muted`, ~20 lines
  - [ ] Fallback if declined: bare unstyled `<aside>`, correct either way

## Backlog

- [ ] **Consumer upgrades**: nothing is forced, submodule pins hold
  - [ ] WEB-Django: add a Jinja2 backend, regenerate `experiences`, move the pin
  - [ ] Publish `1.0.0` to PyPI once the gold test passes

- [ ] **Generator output improvements**
  - [ ] Emit startr.swap attributes — `data-swap` region, `data-swap-target`
  - [ ] Slim the views emitter, ~200 lines of pass-through `super()` overrides
  - [ ] Port `technical_4xx` / `registration` / `admin` runtime templates
  - [ ] `ui-` Sprig fragment variant, checked by `validate_ui_bundle`

- [ ] **`--scripting` lane for audited Sprigs**
  - [ ] Small inline `<script>`, under 16 kB, no `src=`
  - [ ] Never hyperscript — refused whatever the admin grant says

- [ ] **Upstream sweep**: elements startr.style base does not cover
  - [ ] Audit `summary`, `ins`/`del`, `dialog`, `output`, `progress`, `meter`, `abbr`
  - [ ] Fix only the gaps the generator actually hits

## Bugs

- [ ] **reastate: `url()` global is bare `reverse`** — latent, will bite #bug
  - [ ] `{{ url('crm:lead-detail', pk) }}` raises `ImproperlyConfigured`
  - [ ] Positional arg lands in the `urlconf` slot
  - [ ] Fix: adopt the varargs wrapper from `django_startr/jinja2env.py`

- [ ] **WEB-Django: submodule working tree is empty** #bug
  - [ ] `git status` in `our_submodules/STARTR-django-code` shows every file `D`
  - [ ] `make it_startr` cannot work in that state
  - [ ] Confirm whether this is local-only before filing upstream

## Done

> Completed items move to `docs/completed-todos.md` periodically.

- [x] **Packaging repair** — the break was structural, not cosmetic
  - [x] `.gitignore` bare `__init__.py` line ignored EVERY package init
  - [x] Added the four missing `__init__.py` files
  - [x] `find_packages` replaces hand-listed `['django_startr']`
  - [x] `setup.py` read `README.rst`, which does not exist
  - [x] Version single-sourced in `django_startr/__init__.py`

- [x] **Makefile via `/startr-init`** with three project gates
  - [x] `pkg_check` refuses a missing package init
  - [x] `stub_check` refuses leftover DTL escaping machinery
  - [x] `csp_check` refuses an interpreted script attribute
  - [x] `version_check` refuses tag/`__version__` drift

- [x] **SPK1 — the delimiter spike.** Kill criterion did not fire
  - [x] `metaenv.py`: `[% %]` / `[[ ]]`, autoescape off, `StrictUndefined`
  - [x] `{{ csrf_input }}` verified by rendering, not by reading Django
  - [x] `{{ form.as_p }}` renders `bound method` silently — trap confirmed
  - [x] `url()` needs a varargs wrapper, not bare `reverse`
  - [x] `user` is undefined under the Jinja2 backend; use `request.user`

- [x] **Engine repairs**
  - [x] `startry.py:39` hardcoded container path → `settings.ROOT_URLCONF`
  - [x] Debug-URL check moved BEFORE any write, so a failure leaves no half-app
  - [x] Dropped `six`, `__future__`, `(object)`, unused `Context` import
  - [x] `base_template` and `project_base_template` kept distinct

- [x] **All six HTML stubs converted to Jinja2**
  - [x] `create.html`, `list.html`, `base.html`, `detail.html`, `update.html`, `delete.html`
  - [x] `make stub_check` red before, green after
  - [x] Hyperscript gone; `onsubmit="return confirm(…)"` gone with it
  - [x] Delete confirms via the delete page, so no scripting grant is needed

- [x] **All six Python emitters converted**
  - [x] `forms`, `urls`, `admin`, `views`, `__init__views`, `__init__urls`
  - [x] `|join:", "` → `|join(', ')`, `.items` → `.items()`, `forloop` → `loop`
  - [x] `__init__urls` rewritten: a line ending in a meta block tag lost its
        newline to `trim_blocks` and joined two urlpatterns onto one line

- [x] **Server-side search** replaces the hyperscript filter
  - [x] `SEARCH_FIELDS` introspected from text-ish concrete field types
  - [x] Words ANDed, fields ORed, `.distinct()` for the join case
  - [x] Works with JavaScript off; the old filter lied past page one

- [x] **Local dev environment via pipenv** — no Dockerfile needed
  - [x] `Pipfile` mirrors `setup.py` install_requires; python 3.11 like WEB-Django
  - [x] `make dev_install` builds it, `make env_check` refuses a silent skip
  - [x] All 17 tests run, 0 skipped — django 4.2.30, jinja2 3.1.6
  - [x] Proved the fail-closed dev-note guard fails when deliberately broken

- [x] **Test suite and `make test`**
  - [x] 17 tests, 0 skipped; meta layer needs only Jinja2
  - [x] Every test records the failure that motivated it

- [x] **TodoScope alignment**
  - [x] `TODO.md` created to convention
  - [x] `.todoscope-exclude.csv` created
