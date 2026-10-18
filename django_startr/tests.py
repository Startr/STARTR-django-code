"""Gates on the decisions this package makes, not coverage for its own sake.

Every test here exists because something failed once, in a way that did not
raise. Read the docstrings before deleting one.

The suite splits deliberately. The META layer is pure Jinja2 and needs no
Django, so the bulk of the migration gates run anywhere. The RUNTIME layer
(devnotes, jinja2env) needs Django and skips when it is absent — app
dependencies are installed in a container, never into a local interpreter.

    python3 -m unittest django_startr.tests -v
"""

import ast
import re
import unittest

from .metaenv import render_stub

try:
    import django  # noqa: F401
    HAS_DJANGO = True
except ImportError:
    HAS_DJANGO = False


#: The admin's engine as a project sets it up. A test that changes TEMPLATES
#: starts from this, so a missing piece is the piece the test removed.
DJANGO_ENGINE = {
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
    ]},
}


def configure_django():
    """One settings.configure for the whole suite, done at import.

    The column picker and the nav both read the app registry, so they need a
    configured Django and a model to look at — not a mock. Models declared
    below with ``app_label = "django_startr"`` register into this package's own
    app config, which is why no fixture app has to ship in the distribution.
    """
    from django.conf import settings
    if not settings.configured:
        settings.configure(
            DEBUG=False,
            USE_TZ=True,
            DATABASES={},
            ROOT_URLCONF="django_startr.tests",
            # The install order the admin skin documents: the skin before the admin
            # (it must win admin/base_site.html), django_startr after it (its
            # generic registration/*.html must not shadow the admin's own).
            INSTALLED_APPS=[
                "django_startr.admin_skin",
                "django.contrib.contenttypes",
                "django.contrib.auth",
                "django.contrib.admin",
                "django.contrib.messages",
                "django_startr",
            ],
            TEMPLATES=[DJANGO_ENGINE],
            STATIC_URL="/static/",
        )
        django.setup()


if HAS_DJANGO:
    from django.conf import settings as _settings

    #: Whether this suite owns the Django configuration.
    #:
    #: A consuming project's ``manage.py test`` discovers this module and runs
    #: it under THAT project's settings. The fixture models below would then
    #: register into the project's app registry and its test runner would
    #: create tables for them, and the nav tests would walk the project's
    #: urlconf instead of the fixture one. Measured against Trellis, where all
    #: eight nav tests failed and four fixture models quietly became real.
    #:
    #: So the Django-dependent tests run only where this package configured
    #: Django itself, which is its own ``make test``.
    STANDALONE = not _settings.configured
else:
    STANDALONE = False

if STANDALONE:
    configure_django()

    from django.db import models
    from django.urls import include, path, re_path

    class Maker(models.Model):
        name = models.CharField(max_length=50)

        class Meta:
            app_label = "django_startr"

    class Widget(models.Model):
        """One field of every kind the column picker has to rank or refuse."""

        maker = models.ForeignKey(Maker, on_delete=models.CASCADE)
        name = models.CharField(max_length=50)
        nickname = models.CharField(max_length=50, blank=True, default="")
        status = models.CharField(max_length=8, choices=[("new", "New"), ("old", "Old")])
        due_on = models.DateField(null=True, blank=True)
        flagged = models.BooleanField(default=False)
        notes = models.TextField(blank=True, default="")
        extra = models.JSONField(default=dict)
        created_at = models.DateTimeField(auto_now_add=True)

        class Meta:
            app_label = "django_startr"
            verbose_name_plural = "widgets"

    class AppendOnlyModel(models.Model):
        """Stands in for a consuming project's own append-only base."""

        class Meta:
            abstract = True
            app_label = "django_startr"

    class Ledger(AppendOnlyModel):
        memo = models.CharField(max_length=50)

        class Meta:
            app_label = "django_startr"

    class Sealed(models.Model):
        memo = models.CharField(max_length=50)

        class Startr:
            readonly = True

        class Meta:
            app_label = "django_startr"

    def _view(request):  # pragma: no cover - never called, only resolved
        raise NotImplementedError

    _app_patterns = [
        re_path(r"^widgets/$", _view, name="widget_list"),
        re_path(r"^widgets/(?P<pk>\d+)/$", _view, name="widget_detail"),
        # A hand-written list route, hyphenated. Trellis has one of each
        # spelling in the same urlconf, so the nav must find both.
        re_path(r"^makers/$", _view, name="maker-list"),
        re_path(r"^ledgers/$", _view, name="ledger_list"),
        # Not a list route. Must not appear on its own.
        re_path(r"^queue/$", _view, name="queue"),
    ]

    urlpatterns = [
        path("app/", include((_app_patterns, "django_startr"), namespace="django_startr")),
    ]

HTML_STUBS = ["base.html", "list.html", "detail.html", "create.html",
              "update.html", "delete.html"]
PY_STUBS_PER_MODEL = ["views", "urls"]
PY_STUBS_PER_APP = ["forms", "admin", "__init__views", "__init__urls"]

MODEL_CTX = {
    "app_label": "crm", "model_name": "Party", "model_name_slug": "party",
    "model_name_plural": "Parties", "model_name_plural_slug": "parties",
    "model_fields": ["name", "notes"], "searchable_fields": ["name", "notes"],
    "lookup_field": "pk", "slug_field": None, "slug_field_name": "slug",
    "base_template": "crm/party_base.html", "project_base_template": "_shell.html",
    "list_fields": [
        {"name": "party_type", "label": "Party type", "internal_type": "ForeignKey",
         "is_relation": True, "nullable": True},
        {"name": "created_at", "label": "Created at", "internal_type": "DateTimeField",
         "is_relation": False, "nullable": False},
        {"name": "retired", "label": "Retired", "internal_type": "BooleanField",
         "is_relation": False, "nullable": False},
    ],
    "list_related_args": '"party_type"',
    "readonly": False,
    "delete_confirm": "page",
    "delete_button_style": "--size: 0.6rem; --p: 0.4rem; --ml: 1rem;",
}

#: The three second steps, so a test can render all of them.
CONFIRM_MODES = ("page", "inline", "dialog")

#: The same model, append-only. A read-only model gets list and detail and
#: nothing else, so it renders three templates rather than six.
READONLY_CTX = dict(MODEL_CTX, readonly=True, list_related_args="")

READONLY_HTML_STUBS = ["base.html", "list.html", "detail.html"]
APP_CTX = {
    "app_label": "crm",
    "app_module": "crm",
    "model_names": {"Party": ["name", "notes"], "Lead": ["party"]},
    "model_name_slugs": ["party_views", "lead_views"],
    "model_names_dict": {"party": "parties", "lead": "leads"},
}

META_DELIMITERS = ("[[", "]]", "[%", "%]", "[#", "#]")


class MetaLayerTest(unittest.TestCase):
    """The meta layer must never leak into what it emits."""

    def test_no_meta_delimiter_survives_in_any_stub(self):
        for stub in HTML_STUBS + PY_STUBS_PER_MODEL:
            with self.subTest(stub=stub):
                out = render_stub(stub, MODEL_CTX)
                for d in META_DELIMITERS:
                    self.assertNotIn(d, out, f"{stub} leaked {d!r}")
        for stub in PY_STUBS_PER_APP:
            with self.subTest(stub=stub):
                out = render_stub(stub, APP_CTX)
                for d in META_DELIMITERS:
                    self.assertNotIn(d, out, f"{stub} leaked {d!r}")

    def test_a_mistyped_meta_variable_raises_rather_than_rendering_empty(self):
        """StrictUndefined earns its keep here.

        Without it a typo renders as empty string and ships a template that is
        wrong in a way nobody notices until a page 404s. Caught in development
        by exactly this test failing to fail.
        """
        from jinja2 import UndefinedError
        broken = {k: v for k, v in MODEL_CTX.items() if k != "model_name"}
        with self.assertRaises(UndefinedError):
            render_stub("create.html", broken)

    def test_emitted_jinja2_syntax_passes_through_untouched(self):
        out = render_stub("create.html", MODEL_CTX)
        self.assertIn("{% extends", out)
        self.assertIn("{{ csrf_input }}", out)


class NoDtlMachineryTest(unittest.TestCase):
    """The DTL escaping machinery is the thing being removed.

    Its absence is the only honest completion test for the migration, because
    a half-converted stub still renders — it just renders the wrong thing.
    """

    def test_no_stub_carries_templatetag_or_verbatim(self):
        import pathlib
        stub_dir = pathlib.Path(__file__).parent / "templates" / "django_startr"
        for path in sorted(stub_dir.iterdir()):
            if path.is_dir():
                continue
            with self.subTest(stub=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("templatetag", text)
                self.assertNotIn("{% verbatim %}", text)

    def test_no_dtl_only_construct_reaches_the_emitted_layer(self):
        for stub in HTML_STUBS:
            with self.subTest(stub=stub):
                out = render_stub(stub, MODEL_CTX)
                self.assertNotIn("{% csrf_token %}", out)
                self.assertNotIn("{% empty %}", out)
                self.assertNotRegex(out, r"\{%\s*url\s")


class CspSafetyTest(unittest.TestCase):
    """Generated markup must survive AI-UI's ui-Sprig validator.

    ui_dispatch.py refuses hyperscript's three attribute forms BEFORE the admin
    grant gate and unconditionally, because an interpreted attribute is
    invisible to a Content-Security-Policy. A generated page carrying one can
    never be grafted, whatever permission an admin grants.
    """

    HYPERSCRIPT = re.compile(r"(?:^|\s)(?:_|script|data-script)\s*=", re.I)
    INLINE_HANDLER = re.compile(r"\son[a-z]+\s*=", re.I)
    EXTERNAL_REF = re.compile(
        r"(?:src|href|action|data|poster|formaction)\s*=\s*[\"']?\s*(?:https?:|//)", re.I)

    def test_no_interpreted_script_attribute_in_generated_markup(self):
        for stub in HTML_STUBS:
            with self.subTest(stub=stub):
                self.assertIsNone(self.HYPERSCRIPT.search(render_stub(stub, MODEL_CTX)))

    def test_no_inline_event_handler_in_generated_markup(self):
        """The old detail/update/list stubs shipped onsubmit="return confirm(…)".

        That one IS grantable, unlike hyperscript — but a generator should not
        make every consumer spend an admin grant on a confirm dialog.
        """
        for stub in HTML_STUBS:
            with self.subTest(stub=stub):
                self.assertIsNone(self.INLINE_HANDLER.search(render_stub(stub, MODEL_CTX)))

    def test_no_off_origin_reference_in_generated_markup(self):
        for stub in HTML_STUBS:
            with self.subTest(stub=stub):
                self.assertIsNone(self.EXTERNAL_REF.search(render_stub(stub, MODEL_CTX)))


class GeneratedPythonTest(unittest.TestCase):
    """A stub that emits Python must emit Python that parses.

    __init__urls failed this once: a content line ending in a meta block tag
    lost its newline to trim_blocks, joining two urlpatterns entries onto one
    line. The module still "rendered" — it just would not import.
    """

    def test_per_model_emitters_produce_parseable_modules(self):
        for stub in PY_STUBS_PER_MODEL:
            with self.subTest(stub=stub):
                ast.parse(render_stub(stub, MODEL_CTX))

    def test_per_app_emitters_produce_parseable_modules(self):
        for stub in PY_STUBS_PER_APP:
            with self.subTest(stub=stub):
                ast.parse(render_stub(stub, APP_CTX))

    def test_a_nested_app_includes_by_module_path_not_by_label(self):
        """crm.record has the label "record", and include("record.urls.…")
        raises ModuleNotFoundError at the first request. Measured against
        Trellis, where four sub-apps are nested under crm."""
        nested = dict(APP_CTX, app_label="record", app_module="crm.record")
        out = render_stub("__init__urls", nested)
        self.assertIn("include('crm.record.urls.party_urls')", out)
        self.assertIn('app_name = "record"', out)
        ast.parse(out)

    def test_generated_list_view_searches_server_side(self):
        out = render_stub("views", MODEL_CTX)
        self.assertIn("SEARCH_FIELDS = ['name', 'notes']", out)
        self.assertIn('self.request.GET.get("q", "")', out)
        self.assertIn("return queryset.distinct()", out)


class JinjaCallableTest(unittest.TestCase):
    """Jinja2 does not auto-call. The failure is silent, so assert on output."""

    def test_form_rendering_is_called_not_referenced(self):
        out = render_stub("create.html", MODEL_CTX)
        self.assertIn("{{ form.as_p() }}", out)
        self.assertNotIn("{{ form.as_p }}", out)

    def test_paginator_predicates_are_called(self):
        out = render_stub("list.html", MODEL_CTX)
        for name in ("has_previous", "has_next", "previous_page_number",
                     "next_page_number"):
            if name in out:
                self.assertIn(f"{name}()", out,
                              f"{name} referenced without parentheses; Jinja2 "
                              f"renders a bound method and raises nothing")

    def test_auth_check_uses_request_user(self):
        """Django's Jinja2 backend injects request, csrf_token and csrf_input,
        and does NOT run context processors. A bare `user` is undefined."""
        for stub in HTML_STUBS:
            out = render_stub(stub, MODEL_CTX)
            with self.subTest(stub=stub):
                self.assertNotRegex(out, r"\{%\s*if\s+user\.")


@unittest.skipUnless(HAS_DJANGO, "Django not installed; run this suite in a container")
class RuntimeLayerTest(unittest.TestCase):
    """The runtime layer: what generated templates rely on at render time."""

    @classmethod
    def setUpClass(cls):
        from django.conf import settings
        if not settings.configured:
            settings.configure(DEBUG=False, ROOT_URLCONF=None, USE_TZ=True)

    def test_url_global_takes_route_arguments_positionally(self):
        """Bare django.urls.reverse is the wrong global.

        reverse(viewname, urlconf=None, args=None, kwargs=None), so
        `url('app:detail', obj.pk)` passes the pk as urlconf and Django raises
        ImproperlyConfigured naming neither the template nor the mistake.
        """
        import inspect
        from .jinja2env import url
        params = list(inspect.signature(url).parameters.values())
        self.assertEqual(params[1].kind, inspect.Parameter.VAR_POSITIONAL)

    def test_dev_notes_render_nothing_when_debug_is_off(self):
        """Fails closed, unlike the 11ty original.

        Sage.is tests NODE_ENV != 'production', so a forgotten variable ships
        authoring notes to production. DEBUG defaults to False, so silence is
        the default here.
        """
        from django.test import override_settings
        from .devnotes import devnote
        with override_settings(DEBUG=False):
            self.assertEqual(str(devnote("internal note")), "")
        with override_settings(DEBUG=True):
            self.assertIn("internal note", str(devnote("internal note")))

    def test_dev_notes_carry_no_inline_style_and_no_hex_colour(self):
        """Elements before props. startr.style styles standard HTML already,
        so a note is a plain <aside> and the styling gap belongs upstream."""
        from django.test import override_settings
        from .devnotes import devnote
        with override_settings(DEBUG=True):
            html = str(devnote("x"))
        self.assertNotIn("style=", html)
        self.assertNotRegex(html, r"#[0-9a-fA-F]{3,6}\b")
        self.assertIn("<aside", html)


@unittest.skipUnless(HAS_DJANGO, "Django not installed; run this suite in a container")
class AdminBrandTest(unittest.TestCase):
    """Every consumer's admin said "Django administration" (2026-09-28)."""

    def test_an_untouched_site_becomes_startr_admin(self):
        from django.contrib.admin import AdminSite
        from .apps import DEFAULT_ADMIN_TITLE, brand_admin
        site = AdminSite()
        brand_admin(site, DEFAULT_ADMIN_TITLE)
        self.assertEqual((site.site_header, site.site_title), ("Startr Admin", "Startr Admin"))

    def test_a_title_the_project_set_is_kept(self):
        """A subclass attribute and an instance attribute both win, as in Tony's our_site."""
        from django.contrib.admin import AdminSite
        from .apps import brand_admin

        class ProjectSite(AdminSite):
            site_title = "Education Admin Portal"

        site = ProjectSite()
        site.site_header = "Our Admin"
        brand_admin(site, "Startr Admin")
        self.assertEqual((site.site_header, site.site_title), ("Our Admin", "Education Admin Portal"))


class ListColumnTest(unittest.TestCase):
    """A list row must say more than the object's __str__.

    Trellis shipped /crm/tasks/ as a column of bare titles: no lead, no owner,
    no due date, no done state. The stub rendered {{ object }} and nothing
    else, so every list in every startr project was only as legible as that
    model's __str__ — and widening __str__ instead would have lengthened every
    ForeignKey dropdown and every log line with it.
    """

    def test_every_column_reaches_the_generated_markup(self):
        out = render_stub("list.html", MODEL_CTX)
        for column in MODEL_CTX["list_fields"]:
            with self.subTest(column=column["name"]):
                self.assertIn('<th scope="col">%s</th>' % column["label"], out)
                self.assertIn("party.%s" % column["name"], out)

    def test_the_identity_link_survives_beside_the_columns(self):
        out = render_stub("list.html", MODEL_CTX)
        self.assertIn("{{ party }}", out)
        self.assertIn('id="party_list"', out)

    def test_a_boolean_renders_as_a_mark_not_the_word_True(self):
        out = render_stub("list.html", MODEL_CTX)
        self.assertIn("{% if party.retired %}\u2713{% endif %}", out)

    def test_an_empty_cell_renders_a_dash_as_a_literal_character(self):
        """An HTML entity inside {{ }} is escaped, and ships &amp;mdash;.

        The entity form renders correctly in a browser only when it is literal
        template text. Inside an expression Django's Jinja2 backend escapes the
        ampersand, so the page shows the entity source. Measured, not assumed.
        """
        out = render_stub("list.html", MODEL_CTX)
        self.assertIn('{{ party.party_type or "\u2014" }}', out)
        self.assertNotIn("&mdash;", out)

    def test_a_json_list_column_joins_rather_than_printing_a_repr(self):
        """Reachable only when a model names a JSONField in Startr.list_fields.
        A list of addresses is the case worth having; a dict or a string is
        printed as it is, because joining either is wrong."""
        ctx = dict(MODEL_CTX, list_fields=[
            {"name": "emails", "label": "Emails", "internal_type": "JSONField",
             "is_relation": False, "nullable": False}])
        out = render_stub("list.html", ctx)
        self.assertIn('party.emails|join(", ")', out)
        self.assertIn("party.emails is mapping or party.emails is string", out)

    def test_the_empty_row_spans_every_column(self):
        out = render_stub("list.html", MODEL_CTX)
        # three columns, the identity column, and the actions column
        self.assertIn('colspan="5"', out)
        self.assertIn('colspan="4"', render_stub("list.html", READONLY_CTX))

    def test_a_wide_table_scrolls_inside_itself_not_the_page(self):
        """--ofx is startr.style's overflow-x. An inline prop the framework
        does not define is a silent no-op: the page renders, the table
        overflows the body, and nothing says so."""
        out = render_stub("list.html", MODEL_CTX)
        self.assertIn("--ofx:auto", out)
        self.assertNotIn("--ov-x", out)

    def test_the_list_view_prefetches_the_relations_it_renders(self):
        """Without this the page issues one extra query per row per relation,
        and the cost only shows up once a list has real rows in it."""
        out = render_stub("views", MODEL_CTX)
        self.assertIn('queryset = queryset.select_related("party_type")', out)
        self.assertNotIn("select_related", render_stub("views", READONLY_CTX))


class ReadOnlyTest(unittest.TestCase):
    """An append-only model must not be offered an edit form.

    The failure is not cosmetic. The form saves, the row appends, and the page
    reports an update that did not happen.
    """

    def test_no_write_route_is_emitted(self):
        out = render_stub("urls", READONLY_CTX)
        for name in ("party_create", "party_update", "party_delete"):
            self.assertNotIn(name, out)
        self.assertIn("party_list", out)
        self.assertIn("party_detail", out)
        ast.parse(out)

    def test_no_write_view_is_emitted(self):
        out = render_stub("views", READONLY_CTX)
        classes = [node.name for node in ast.parse(out).body
                   if isinstance(node, ast.ClassDef)]
        self.assertEqual(classes, ["PartyListView", "PartyDetailView"])

    def test_no_page_links_to_a_route_that_does_not_exist(self):
        """A link to a route the urls module no longer emits is not an ugly
        link. It is a NoReverseMatch, and the whole page 500s."""
        for stub in READONLY_HTML_STUBS:
            out = render_stub(stub, READONLY_CTX)
            with self.subTest(stub=stub):
                for name in ("party_create", "party_update", "party_delete"):
                    self.assertNotIn(name, out)

    def test_the_destructive_step_is_always_a_post(self):
        """Whatever the mode, the row goes on a POST and never on a GET.

        In page mode the control is a link, but it links to the confirm page;
        the POST is there. The stub used to link straight at the delete view,
        whose own get() raised Http404, so the link was simply dead.
        """
        for mode in CONFIRM_MODES:
            page = "delete.html" if mode == "page" else "list.html"
            out = render_stub(page, dict(MODEL_CTX, delete_confirm=mode))
            with self.subTest(mode=mode, stub=page):
                self.assertIn('method="post"', out)
                self.assertIn("{{ csrf_input }}", out)

    def test_a_project_delete_gate_is_honoured_and_optional(self):
        """default(true) so a project without a gate sees no change, and one
        with a gate has it respected on both pages."""
        for stub in ("list.html", "detail.html"):
            with self.subTest(stub=stub):
                self.assertIn("delete_allowed|default(true)",
                              render_stub(stub, MODEL_CTX))

    def test_the_editable_case_still_emits_all_five(self):
        classes = [node.name for node in ast.parse(render_stub("views", MODEL_CTX)).body
                   if isinstance(node, ast.ClassDef)]
        self.assertEqual(classes, ["PartyListView", "PartyDetailView", "PartyCreateView",
                                   "PartyUpdateView", "PartyDeleteView"])


class DeleteControlTest(unittest.TestCase):
    """The delete control: small, guarded, and never a one-click destroy.

    The generator has always written a <model>_delete.html confirm page that
    nothing could reach — the controls posted straight at the delete URL and
    the view raised Http404 on GET. Three modes now, and all three end in a
    POST behind a second step.
    """

    PAGES = ("list.html", "detail.html", "update.html")

    def ctx(self, mode, **extra):
        return dict(MODEL_CTX, delete_confirm=mode, **extra)

    def test_every_page_carries_the_agreed_button_style(self):
        for mode in CONFIRM_MODES:
            for stub in self.PAGES:
                with self.subTest(mode=mode, stub=stub):
                    out = render_stub(stub, self.ctx(mode))
                    self.assertIn("--size: 0.6rem; --p: 0.4rem; --ml: 1rem;", out)

    def test_only_page_mode_offers_a_link_and_it_goes_to_the_confirm_page(self):
        """A delete a link can reach is a delete a crawler can perform, so the
        two script-free modes emit no anchor at all. Page mode's anchor is
        safe because the view renders a form there rather than deleting."""
        link = re.compile(r"<a[^>]+party_delete")
        self.assertIsNotNone(link.search(render_stub("list.html", self.ctx("page"))))
        for mode in ("inline", "dialog"):
            for stub in self.PAGES:
                with self.subTest(mode=mode, stub=stub):
                    self.assertIsNone(link.search(render_stub(stub, self.ctx(mode))))

    def test_page_mode_links_to_the_confirm_page_and_the_view_serves_it(self):
        for stub in self.PAGES:
            self.assertIn("party_delete", render_stub(stub, self.ctx("page")))
        views = render_stub("views", self.ctx("page"))
        self.assertNotIn("raise Http404", views)
        self.assertNotIn("from django.http import Http404", views)

    def test_the_other_modes_keep_the_confirm_page_unreachable_by_get(self):
        for mode in ("inline", "dialog"):
            views = render_stub("views", self.ctx(mode))
            with self.subTest(mode=mode):
                self.assertIn("raise Http404", views)
                self.assertIn("from django.http import Http404", views)
                ast.parse(views)

    def test_inline_mode_asks_in_place_without_script(self):
        out = render_stub("list.html", self.ctx("inline"))
        self.assertIn("<details", out)
        self.assertIn("Delete {{ party }}?", out)
        self.assertNotIn("delete-dialog.js", out)

    def test_dialog_mode_loads_its_script_once_not_once_per_row(self):
        out = render_stub("list.html", self.ctx("dialog"))
        self.assertEqual(out.count("delete-dialog.js"), 1)
        self.assertIn("data-confirm-delete", out)

    def test_dialog_modes_script_is_shipped_with_the_package(self):
        """An unshipped static file is a 404 at the point of deleting, and
        nothing on the page says so — the form just posts unconfirmed."""
        import pathlib
        root = pathlib.Path(__file__).resolve().parent
        script = root / "static" / "django_startr" / "delete-dialog.js"
        self.assertTrue(script.is_file(), "the dialog script is missing")
        manifest = (root.parent / "MANIFEST.in").read_text(encoding="utf-8")
        self.assertIn("recursive-include django_startr/static", manifest)

    def test_the_shared_control_partial_is_shipped(self):
        """It has no extension, which is exactly the kind of file a packaging
        glob drops."""
        import pathlib
        root = pathlib.Path(__file__).resolve().parent
        self.assertTrue((root / "templates" / "django_startr" / "_delete_control").is_file())
        manifest = (root.parent / "MANIFEST.in").read_text(encoding="utf-8")
        self.assertIn("recursive-include django_startr/templates *", manifest)

    def test_no_mode_reintroduces_an_inline_handler(self):
        """The old stub shipped onsubmit="return confirm(…)". Dialog mode is
        the reason to check again: it is the one that wanted a script."""
        handler = re.compile(r"\son[a-z]+\s*=", re.I)
        for mode in CONFIRM_MODES:
            for stub in self.PAGES + ("delete.html",):
                with self.subTest(mode=mode, stub=stub):
                    self.assertIsNone(handler.search(render_stub(stub, self.ctx(mode))))

    def test_every_control_is_behind_both_guards(self):
        for mode in CONFIRM_MODES:
            for stub in self.PAGES:
                with self.subTest(mode=mode, stub=stub):
                    out = render_stub(stub, self.ctx(mode))
                    self.assertIn(
                        "{% if request.user.is_authenticated and delete_allowed|default(true) %}",
                        out)

    def test_a_read_only_model_gets_no_control_in_any_mode(self):
        for mode in CONFIRM_MODES:
            for stub in ("list.html", "detail.html"):
                with self.subTest(mode=mode, stub=stub):
                    out = render_stub(stub, self.ctx(mode, readonly=True))
                    self.assertNotIn("party_delete", out)
                    self.assertNotIn("delete-dialog.js", out)

    def test_the_confirm_page_names_the_damage_and_refuses_a_blocked_row(self):
        out = render_stub("delete.html", MODEL_CTX)
        self.assertIn("delete_summary.blocked", out)
        self.assertIn("delete_summary.deletes", out)
        self.assertIn("delete_summary.clears", out)
        self.assertIn("delete_summary.protected", out)
        # The Confirm button lives inside the not-blocked branch only.
        blocked, _, allowed = out.partition("{% else %}")
        self.assertNotIn('value="Confirm"', blocked)
        self.assertIn('value="Confirm"', allowed)


@unittest.skipUnless(STANDALONE, "not this package's own settings; run make test here")
class ColumnPickerTest(unittest.TestCase):
    """What the generator guesses, measured against a real model."""

    def setUp(self):
        from .startry import Startr
        self.startr = Startr()

    def test_columns_are_ranked_and_capped(self):
        """FK first, then choice, then date, then boolean. Four at most, because
        a fifth column is where a list stops being scannable."""
        names = [c["name"] for c in self.startr.get_list_field_names(Widget)]
        self.assertEqual(names, ["maker", "status", "due_on", "flagged"])

    def test_prose_and_structures_never_become_a_cell(self):
        names = [c["name"] for c in self.startr.get_list_field_names(Widget)]
        self.assertNotIn("notes", names)   # TextField
        self.assertNotIn("extra", names)   # JSONField
        self.assertNotIn("created_at", names)  # auto_now_add
        self.assertNotIn("id", names)

    def test_labels_are_sentence_case_from_the_verbose_name(self):
        labels = {c["name"]: c["label"] for c in self.startr.get_list_field_names(Widget)}
        self.assertEqual(labels["due_on"], "Due on")
        self.assertEqual(labels["maker"], "Maker")

    def test_blank_counts_as_nullable_for_a_cell(self):
        """A CharField(blank=True, default="") renders as nothing at all, which
        reads as a broken cell rather than an empty one."""
        columns = {c["name"]: c for c in self.startr.get_list_field_names(Widget)}
        self.assertTrue(columns["due_on"]["nullable"])
        self.assertFalse(columns["flagged"]["nullable"])

    def test_a_model_can_name_its_own_columns(self):
        """A correction in the generated file does not survive a regeneration,
        and changing STARTR_DELETE_CONFIRM regenerates every page."""
        class Picked(Widget):
            class Startr:
                list_fields = ["nickname", "maker"]

            class Meta:
                proxy = True
                app_label = "django_startr"

        columns = self.startr.get_list_field_names(Picked)
        self.assertEqual([c["name"] for c in columns], ["nickname", "maker"])
        self.assertEqual(columns[0]["label"], "Nickname")
        self.assertTrue(columns[1]["is_relation"])

    def test_the_delete_summary_qualifies_a_name_that_appears_twice(self):
        """Trellis deletes a party and clears "1 link, 1 action, 1 link" —
        crm.Link and identity.Link. The reader learns nothing from that."""
        from django_startr.deletion import _phrases
        self.assertEqual(_phrases([(Widget, 1), (Maker, 2)]),
                         ["1 widget", "2 makers"])
        qualified = _phrases([(Widget, 1), (Widget, 2)])
        self.assertTrue(all(p.count("django_startr") == 1 for p in qualified), qualified)

    def test_read_only_is_recognised_three_ways(self):
        self.assertTrue(self.startr.is_readonly(Ledger))   # append-only base
        self.assertTrue(self.startr.is_readonly(Sealed))   # class Startr
        self.assertFalse(self.startr.is_readonly(Widget))


@unittest.skipUnless(STANDALONE, "not this package's own settings; run make test here")
class NavTest(unittest.TestCase):
    """Mounting a model and linking to it were two unrelated acts.

    Trellis ran for months with /crm/tasks/ answering 200 and no link to it
    anywhere, because nothing connected the two. The nav is derived from the
    resolver so it cannot go stale.
    """

    class _User:
        def __init__(self, authenticated=True, perms=()):
            self.is_authenticated = authenticated
            self._perms = set(perms)

        def has_perm(self, perm):
            return perm in self._perms

    class _Request:
        def __init__(self, user):
            self.user = user

    def setUp(self):
        from django_startr import nav
        self.nav = nav
        nav.reset_cache()

    def labels(self, user):
        return [item["label"] for item in self.nav.nav_items(self._Request(user))]

    def test_every_mounted_list_route_is_found_whatever_its_spelling(self):
        """"lead_list" is the generator's spelling and "lead-list" is what a
        hand-written view gets called. Trellis has both, in one urlconf."""
        self.assertEqual(self.labels(self._User(False)), ["Ledgers", "Makers", "Widgets"])

    def test_a_route_that_is_not_a_list_is_not_a_nav_entry(self):
        self.assertNotIn("Queue", self.labels(self._User(False)))

    def test_urls_resolve(self):
        items = {i["slug"]: i["url"] for i in self.nav.nav_items(self._Request(self._User(False)))}
        self.assertEqual(items["widget"], "/app/widgets/")

    def test_a_viewer_is_not_offered_a_page_their_permissions_refuse(self):
        user = self._User(perms=["django_startr.view_widget"])
        self.assertEqual(self.labels(user), ["Widgets"])

    def test_an_anonymous_viewer_still_sees_pages_that_answer_200(self):
        """A generated list view is unauthenticated out of the box. Hiding a
        page anyone can open would be a lie, so anonymous gets the pass — and a
        project that gates its lists turns it off."""
        from django.test import override_settings
        self.assertEqual(len(self.labels(self._User(False))), 3)
        with override_settings(STARTR_NAV_ANON=False):
            self.assertEqual(self.labels(self._User(False)), [])

    def test_hide_wins_over_everything(self):
        from django.test import override_settings
        with override_settings(STARTR_NAV_HIDE=["ledger"]):
            self.assertEqual(self.labels(self._User(False)), ["Makers", "Widgets"])

    def test_order_puts_named_slugs_first_and_the_rest_alphabetical(self):
        from django.test import override_settings
        with override_settings(STARTR_NAV_ORDER=["widget", "ledger"]):
            self.assertEqual(self.labels(self._User(False)), ["Widgets", "Ledgers", "Makers"])

    def test_a_label_can_be_overridden(self):
        from django.test import override_settings
        with override_settings(STARTR_NAV_LABEL={"widget": "Gizmos"}):
            self.assertIn("Gizmos", self.labels(self._User(False)))

    def test_two_apps_sharing_a_model_name_do_not_share_a_label(self):
        """A nav offering "Links" twice is no better than the hidden page this
        module exists to prevent."""
        from django.test import override_settings
        with override_settings(STARTR_NAV_LABEL={"maker": "Widgets"}):
            labels = self.labels(self._User(False))
        self.assertIn("Widgets", labels)            # set by hand, left alone
        self.assertIn("Django startr widgets", labels)  # the collider moved
        self.assertNotEqual(labels[0], labels[1])

    def test_a_label_can_be_keyed_by_route_name(self):
        """Keying only by slug cannot tell crm:link_list from
        identity:link_list, which is the case that needs it most."""
        from django.test import override_settings
        with override_settings(STARTR_NAV_LABEL={"django_startr:widget_list": "Gizmos"}):
            self.assertIn("Gizmos", self.labels(self._User(False)))

    def test_everything_is_primary_when_a_project_says_nothing(self):
        items = self.nav.nav_items(self._Request(self._User(False)))
        self.assertTrue(all(item["primary"] for item in items))

    def test_ordering_a_few_pages_makes_those_the_primary_ones(self):
        """Mounting every model is the point; nineteen links across the top of
        every page is not. A project that bothered to order five pages has
        already said which five it cares about."""
        from django.test import override_settings
        with override_settings(STARTR_NAV_ORDER=["widget"]):
            items = {i["label"]: i["primary"]
                     for i in self.nav.nav_items(self._Request(self._User(False)))}
        self.assertEqual(items, {"Widgets": True, "Ledgers": False, "Makers": False})

    def test_an_extra_is_primary_unless_a_primary_list_says_otherwise(self):
        from django.test import override_settings
        extra = [("django_startr:queue", "Queue", "is_authenticated")]
        seer = self._User(perms=["django_startr.view_widget",
                                 "django_startr.view_maker",
                                 "django_startr.view_ledger"])
        with override_settings(STARTR_NAV_ORDER=["widget"], STARTR_NAV_EXTRA=extra):
            items = {i["label"]: i["primary"]
                     for i in self.nav.nav_items(self._Request(seer))}
        self.assertTrue(items["Queue"])
        with override_settings(STARTR_NAV_PRIMARY=["ledger"], STARTR_NAV_EXTRA=extra):
            items = {i["label"]: i["primary"]
                     for i in self.nav.nav_items(self._Request(seer))}
        self.assertEqual(items, {"Ledgers": True, "Makers": False,
                                 "Widgets": False, "Queue": False})

    def test_extras_come_last_and_can_ask_for_a_requirement(self):
        from django.test import override_settings
        extra = [("django_startr:queue", "Queue", "is_authenticated")]
        with override_settings(STARTR_NAV_EXTRA=extra):
            self.assertEqual(self.labels(self._User(True))[-1], "Queue")
            self.assertNotIn("Queue", self.labels(self._User(False)))


if __name__ == "__main__":
    unittest.main(verbosity=2)


@unittest.skipUnless(STANDALONE, "not this package's own settings; run make test here")
class NavRenderTest(unittest.TestCase):
    """The dock and the tiers render from the same items, automatically.

    A project gets a working nav on install: the first four primary pages in
    the phone dock, the apps as groups, a generic icon for a page without one,
    the current page marked on every copy of its link. Settings refine.
    """

    def setUp(self):
        from django.test import RequestFactory
        from django_startr import nav
        self.nav = nav
        nav.reset_cache()
        self.factory = RequestFactory()

    def _request(self, path="/app/widgets/"):
        request = self.factory.get(path)
        request.user = NavTest._User(False)
        return request

    @staticmethod
    def _items(n=6, skip_primary=(2,)):
        return [{"slug": f"s{i}", "name": f"n{i}", "url": f"/{i}/", "label": str(i), "primary": i not in skip_primary} for i in range(n)]

    def test_current_marks_every_copy_of_the_longest_prefix(self):
        items = [{"url": "/app/", "label": "Home"}, {"url": "/app/widgets/", "label": "W"}, {"url": "/app/widgets/", "label": "W again"}]
        self.nav.with_current(items, "/app/widgets/3/")
        self.assertEqual([item["current"] for item in items], [False, True, True])

    def test_the_dock_defaults_to_the_first_four_primary_pages(self):
        items = self._items()
        dock = self.nav.dock_items(items)
        self.assertEqual([item["slug"] for item in dock], ["s0", "s1", "s3", "s4"])
        self.assertEqual([item["dock_order"] for item in items], [0, 1, 99, 2, 3, 99])

    def test_the_dock_follows_the_setting_in_its_order(self):
        from django.test import override_settings
        with override_settings(STARTR_NAV_DOCK=["s4", "n0"]):
            self.assertEqual([item["slug"] for item in self.nav.dock_items(self._items())], ["s4", "s0"])

    def test_groups_are_the_apps_and_an_extra_falls_to_pages(self):
        items = self.nav.nav_items(self._request())
        items.append({"name": "home", "slug": "home", "url": "/", "label": "Home", "primary": True})
        groups = self.nav.nav_groups(items)
        self.assertEqual([label for label, _ in groups], ["Django_Startr", "Pages"])
        self.assertEqual([item["label"] for item in groups[0][1]], ["Ledgers", "Makers", "Widgets"])

    def test_a_named_group_comes_first_and_takes_its_members(self):
        from django.test import override_settings
        items = self.nav.nav_items(self._request())
        # Slugs or full route names: "maker" is the slug of django_startr:maker-list.
        with override_settings(STARTR_NAV_GROUPS={"Records": ["widget", "maker"]}):
            groups = self.nav.nav_groups(items)
        self.assertEqual([(label, [i["label"] for i in members]) for label, members in groups],
                         [("Records", ["Makers", "Widgets"]), ("Django_Startr", ["Ledgers"])])

    def test_admin_groups_come_from_the_admin_app_list(self):
        app_list = [{"name": "Crm", "app_label": "crm", "models": [
            {"name": "Leads", "object_name": "Lead", "admin_url": "/admin/crm/lead/"},
            {"name": "No page", "object_name": "Nope", "admin_url": None},
        ]}]
        groups = self.nav.admin_groups(app_list, "/admin/crm/lead/5/change/")
        self.assertEqual([(label, [i["label"] for i in members]) for label, members in groups], [("Crm", ["Leads"])])
        self.assertTrue(groups[0][1][0]["current"])

    def test_the_admin_tail_names_the_page_below_a_list(self):
        groups = [("Crm", [{"label": "Leads", "url": "/admin/crm/lead/", "slug": "lead", "name": "crm.Lead", "primary": True}])]
        tail = self.nav.admin_tail
        self.assertIsNone(tail("/admin/", groups, title="Site administration"))
        self.assertIsNone(tail("/admin/crm/lead/", groups, title="Select lead to change"))
        self.assertEqual(tail("/admin/crm/lead/5/change/", groups, title="Change lead", subtitle="Theodore Zelazny"), "Theodore Zelazny")
        self.assertEqual(tail("/admin/crm/lead/add/", groups, title="Add lead"), "Add lead")
        self.assertEqual(tail("/admin/crm/lead/5/delete/", groups, title="Are you sure?", obj="Theodore Zelazny"), "Theodore Zelazny · Delete")
        self.assertEqual(tail("/admin/crm/lead/5/history/", groups, title="Change history: Theodore Zelazny", obj="Theodore Zelazny"), "Theodore Zelazny · History")

    def test_a_tail_is_the_current_page_and_the_list_keeps_the_pill(self):
        html = self.nav.render_nav(self._request("/app/widgets/3/"), "tiers", tail="Widget 3")
        self.assertIn('data-tiers-tail aria-current="page"', html)
        self.assertIn("Widget 3", html)
        self.assertIn('href="/app/widgets/" data-swap-target="main" data-on', html)
        self.assertNotIn('data-swap-target="main" aria-current="page"', html)

    def test_an_unknown_page_gets_the_generic_icon(self):
        self.assertEqual(self.nav.icon_paths({"slug": "zzz", "name": "zzz"}), self.nav.DEFAULT_ICONS["page"])
        self.assertEqual(self.nav.icon_paths({"slug": "lead", "name": "x"}), self.nav.DEFAULT_ICONS["lead"])

    def test_the_dock_renders_with_its_hooks_and_no_classes(self):
        html = self.nav.render_nav(self._request(), "dock")
        for marker in ("<nav data-dock", "data-dock-items", "data-dock-more", "data-dock-bubble", 'aria-current="page"', "nav-dock.js", "--pe:none", 'data-swap-target="main"'):
            self.assertIn(marker, html)
        self.assertNotIn(' class="', html)

    def test_the_tiers_render_with_one_row_shown(self):
        html = self.nav.render_nav(self._request(), "tiers")
        self.assertIn("<nav data-tiers", html)
        self.assertIn('aria-current="true"', html)
        self.assertEqual(html.count("<div data-row="), html.count(" hidden>") + 1)
        self.assertIn("nav-tiers.js", html)

    def test_the_context_processor_offers_the_rendered_navs(self):
        context = self.nav.startr_nav(self._request())
        self.assertEqual(context["startr_nav_path"], "/app/widgets/")
        self.assertIn("data-dock", context["startr_nav_html"]("dock"))
        self.assertIn("data-tiers", context["startr_nav_html"]("tiers"))
        self.assertTrue(any(item["current"] for item in context["startr_nav"]))


@unittest.skipUnless(STANDALONE, "not this package's own settings; run make test here")
class AdminSkinTest(unittest.TestCase):
    """The admin overrides live in django_startr.admin_skin, listed before the admin.

    Listed ahead of ``django.contrib.admin``, ``django_startr`` also put its
    generic ``registration/logged_out.html`` (which reverses a 'login' route)
    ahead of the admin's own, and Log out answered 500. The skin is an app of
    its own so that ``django_startr`` can sit after the admin.
    """

    def setUp(self):
        from django.contrib.admin import AdminSite
        from django.contrib.auth.models import User
        from django.test import RequestFactory
        from django.urls import set_urlconf

        self.site = AdminSite(name="admin")
        self.site.register(Widget)
        site = self.site

        class Urls:
            urlpatterns = [path("admin/", site.urls)]

        set_urlconf(Urls)
        self.addCleanup(set_urlconf, None)
        self.request = RequestFactory().get("/admin/django_startr/widget/")
        self.request.user = User(username="root", is_active=True, is_staff=True, is_superuser=True)

    def page(self, site=None):
        from django.template.loader import render_to_string
        site = site or self.site
        return render_to_string("admin/base_site.html", {**site.each_context(self.request), "title": "Widgets"}, request=self.request)

    def _site(self):
        from django.contrib.admin import AdminSite
        site = AdminSite(name="admin")
        site.register(Widget)
        return site

    def test_the_skin_is_served_ahead_of_the_admin_and_the_admin_wins_the_rest(self):
        from pathlib import Path
        from django.template.loader import get_template
        skin = Path(__file__).parent / "admin_skin"
        for name in ("admin/base_site.html", "admin/login.html"):
            self.assertTrue(Path(get_template(name).origin.name).resolve().is_relative_to(skin.resolve()), name)
        for name in ("registration/logged_out.html", "registration/password_change_form.html"):
            self.assertIn("django/contrib/admin", get_template(name).origin.name.replace("\\", "/"), name)

    def test_with_the_sidebar_off_the_header_carries_the_tiers(self):
        self.site.enable_nav_sidebar = False
        html = self.page()
        self.assertIn("<nav data-tiers", html)
        self.assertNotIn('id="nav-sidebar"', html)
        self.assertNotIn('class="breadcrumbs"', html)

    def test_with_the_sidebar_on_django_keeps_its_own_nav_and_the_tiers_stay_out(self):
        """The header shows tiers exactly when the sidebar is off: one nav, never two or none."""
        self.site.enable_nav_sidebar = True
        html = self.page()
        self.assertIn('id="nav-sidebar"', html)
        self.assertIn('class="breadcrumbs"', html)
        self.assertNotIn("data-tiers", html)

    def test_the_sidebar_goes_when_the_skin_is_served_and_STARTR_ADMIN_NAV_is_on(self):
        from django.test import override_settings
        from .admin_skin.apps import apply_skin
        site = self._site()
        apply_skin(site)
        self.assertFalse(site.enable_nav_sidebar)
        with override_settings(STARTR_ADMIN_NAV=False):
            site = self._site()
            apply_skin(site)
            self.assertTrue(site.enable_nav_sidebar)
            html = self.page(site)
        self.assertIn('id="nav-sidebar"', html)
        self.assertNotIn("data-tiers", html)

    def test_a_project_override_of_base_site_keeps_the_sidebar_and_is_reported(self):
        import tempfile
        from pathlib import Path
        from django.test import override_settings
        from .admin_skin.apps import apply_skin
        from .admin_skin.checks import check_admin_skin
        self.assertEqual(check_admin_skin(None), [])
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "admin").mkdir()
            (Path(tmp) / "admin" / "base_site.html").write_text('{% extends "admin/base.html" %}')
            with override_settings(TEMPLATES=[dict(DJANGO_ENGINE, DIRS=[tmp])]):
                site = self._site()
                apply_skin(site)
                self.assertTrue(site.enable_nav_sidebar)
                warnings = check_admin_skin(None)
        self.assertEqual([w.id for w in warnings], ["startr.W001"])
        self.assertIn("django_startr.admin_skin", warnings[0].hint)

    def test_the_request_context_processor_is_checked_because_the_sidebar_check_goes_quiet(self):
        """Django's admin.W411 warns about the request processor only while its
        sidebar is on; the skin turns the sidebar off, so startr.W002 speaks."""
        from django.test import override_settings
        from .admin_skin.checks import check_admin_skin
        bare = dict(DJANGO_ENGINE, OPTIONS={"context_processors": ["django.contrib.auth.context_processors.auth"]})
        with override_settings(TEMPLATES=[bare]):
            self.assertEqual([w.id for w in check_admin_skin(None)], ["startr.W002"])
            with override_settings(STARTR_ADMIN_NAV=False):
                self.assertEqual(check_admin_skin(None), [])

    def test_the_skin_owns_the_theme(self):
        """Django's dark_mode.css and theme.js, and the toggle that drives them,
        wrote their palettes over the kit's tokens: a click left the stock
        blue admin. The page loads neither, and the map covers every explicit theme."""
        self.site.enable_nav_sidebar = False
        html = self.page()
        for gone in ("dark_mode.css", "theme.js", "theme-toggle", "color_theme_toggle"):
            self.assertNotIn(gone, html)
        self.assertIn(":root, html[data-theme] {", html)
        self.assertIn('html[data-theme="dark"] { color-scheme: dark; }', html)

    def test_module_headings_paint_the_same_on_django_4_and_5(self):
        """4.2 paints `.module h2` on --primary and 5.2 on --header-bg; the kit
        text colour on the kit primary was unreadable on 4.2."""
        self.assertIn(".module h2, .module caption, .inline-group h2 { background: var(--header-bg); color: var(--header-link-color); }", self.page())

    def test_the_signed_in_name_is_hidden_to_the_eye_not_to_the_screen_reader(self):
        html = self.page()
        self.assertIn('<span class="welcome">', html)
        self.assertIn("root", html.split('class="welcome"', 1)[1].split("</span>", 1)[0])
        self.assertNotIn("--d:none", html.split("<header", 1)[1].split("</header>", 1)[0])
        self.assertIn("#user-tools .welcome { position: absolute;", html)

    def test_smart_select_is_opt_in_and_names_its_input(self):
        from django.test import override_settings
        from .templatetags.smart_select import smart_select_js
        self.assertEqual(smart_select_js(), "")
        self.assertNotIn("convertSelectToSmartSelect", self.page())
        with override_settings(STARTR_ADMIN_SMART_SELECT=True):
            script = smart_select_js()
            self.assertIn("convertSelectToSmartSelect", self.page())
        self.assertIn("label[for=", script)
        self.assertIn("label.htmlFor = input.id", script)
        self.assertIn("aria-label", script)
