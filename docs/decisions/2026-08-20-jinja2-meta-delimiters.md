# Jinja2 meta-delimiters, and three things measured on the way

Date: 2026-08-20 · SPK1 output · Status: accepted

## Question

What is the shortest honest path from the DTL-escaping stubs to templates that
render under Django's Jinja2 backend, and what does that path demand of the
code we are about to write?

## Decision

Render the stubs through a Jinja2 `Environment` on **non-default delimiters**.

| Layer | Statement | Expression | Comment |
|---|---|---|---|
| meta — the stubs | `[% %]` | `[[ ]]` | `[# #]` |
| emitted — the output | `{% %}` | `{{ }}` | `{# #}` |

The two layers no longer collide, so an emitted `{% for %}` is literal text and
needs no escaping. Every `{% templatetag openblock %}` and `{% verbatim %}` in
the package is deleted rather than translated.

Implementation: `django_startr/metaenv.py`. Three settings carry weight:

- `autoescape=False` — this layer emits template *source*, not a page.
  HTML-escaping it would corrupt every quote and ampersand in the file.
- `undefined=StrictUndefined` — a mistyped `[[ model_nmae ]]` must raise, not
  render empty and ship a subtly broken template.
- `keep_trailing_newline=True` — generated files end in a newline like any
  hand-written one.

`create_file_from_template` no longer calls `django.template.loader.get_template`.
That resolves against the *project's* engines, and in a Jinja2-first project the
stub could be claimed by the wrong one. The stubs are not the project's
templates; metaenv owns them.

## Measured

Rendered against a live reastate instance, not read out of Django's source.

### 1. `{{ csrf_input }}` works — no helper needed

Django's Jinja2 backend injects `request`, `csrf_token` and `csrf_input` on
every render. Verified: `<input type="hidden" name="csrfmiddlewaretoken" …>`.
A2 is closed and the kill criterion did not fire.

### 2. `{{ form.as_p }}` fails silently — the trap is real

Jinja2 does not auto-call. Without parentheses the template renders the escaped
text `<bound method RenderableFormMixin.as_p of <PartyForm …>>` and raises
nothing. With `{{ form.as_p() }}` it renders the fields correctly.

A test for this must assert on **rendered output** — the presence of `<input>`
and the absence of `bound method`. A test that only asserts "no exception"
passes on the broken version.

### 3. `url()` must take arguments positionally — a wrapper, not `reverse`

Exposing `django.urls.reverse` directly as the `url` global is wrong, and it
fails in a way that names neither the template nor the mistake.

`reverse(viewname, urlconf=None, args=None, kwargs=None)`. So the obvious
`{{ url('crm:lead-detail', lead.pk) }}` passes the pk as **urlconf**:

```
ImproperlyConfigured: The included URLconf '26' does not appear to have any
patterns in it.
```

`django_startr/jinja2env.py` therefore ships:

```python
def url(name, *args, **kwargs):
    return reverse(name, args=args or None, kwargs=kwargs or None)
```

Swapping the wrapper in made the same template render. **reastate carries this
latent bug today** — `config/jinja2env.py` exposes bare `reverse`, so its first
template to pass a route argument will hit it.

### 4. `user` is undefined under the Jinja2 backend — use `request.user`

Found only because the `url` fix let the render get one step further.

The backend injects `request`, `csrf_token` and `csrf_input`, and **does not run
context processors**. The DTL stubs' `{% if user.is_authenticated %}` therefore
raises `UndefinedError: 'user' is undefined`. Generated templates use
`{% if request.user.is_authenticated %}`, which works because `request` is
injected.

This is not in any DTL→Jinja2 conversion table we started from. It belongs in
`docs/JINJA2-MIGRATION.md`.

## Cost

`create.html` converted in minutes; `list.html`, the heaviest, took longer for
the search redesign rather than the delimiter work. The old `list.html:21` ran
to 600 characters of escaping machinery and has no successor — it did not need
translating, it needed deleting. The stub estimate drops from XL to M.

## Also decided here

**Hyperscript is gone and cannot come back.** `list.html` shipped
`_="on keyup …"`. AI-UI's `ui_dispatch.py:88` refuses all three interpreted
attribute forms *before* the admin grant gate, unconditionally — the grant
covers inline `on*=` handlers and inline `<script>` under 16 kB, and explicitly
never the interpreted forms, "because those are the parts an admin cannot
meaningfully consent to." The replacement is a plain GET form filtering
server-side, which also fixes a bug nobody had named: the old filter only hid
rows already on the page, so it silently lied on every list past page one.

`make csp_check` fails the build if an interpreted attribute reappears. It was
red before this change and is green after, which is the only evidence that it
does anything.

**Two base templates, never conflated.** `base_template` is the per-model file
the five pages extend. `project_base_template` is the site shell that file
extends, read from `settings.STARTR_BASE_TEMPLATE` and defaulting to
`base.html` — reastate's shell is `_shell.html`, so it cannot be a literal.

## Consequences

- `docs/JINJA2-MIGRATION.md` gains two rows nobody predicted: `user` →
  `request.user`, and `url()` needing a varargs wrapper.
- reastate should adopt the same `url` wrapper before it hits the bug.
- The `form.as_p()` gate must assert on rendered output.
