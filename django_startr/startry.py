import os
import re
from importlib import import_module

from django.conf import settings
from django.db.models.fields import SlugField

from .metaenv import render_stub


class Startr:
    """
    Given a dictionary of apps and models, Startr will startr up a bunch of files that will help get your new app up
    and running quickly.
    """

    def startr(self, apps_and_models):
        """
        Iterates a dictionary of apps and models and creates all the necessary files to get up and running quickly.
        """
        # Reported BEFORE anything is written. This used to run last, so a
        # failure here left a half-generated app behind with no way to tell
        # which files were ours.
        self.ensure_debug_urls_in_project()

        for app_label, models_app in apps_and_models.items():
            models, app = models_app
            models = list(models)
            model_names = {model.__name__: self.get_field_names_for_model(model) for model in models}
            self.create_directories(app)
            #self.create_debug_404_template(app)
            self.create_init_files(app, model_names.keys(), models)
            self.remove_empty_startapp_files(app)
            for file_name in ["forms", "admin"]:
                file_path = "%s/%s.py" % (app.path, file_name)
                template_path = "django_startr/%s" % (file_name)
                self.create_file_from_template(file_path, template_path, {"model_names": model_names})
            for model in models:
                model_attributes = self.model_attributes(app, model)
                self.create_files_from_templates(model_attributes)

    def get_field_names_for_model(self, model):
        """
        Returns fields other than id and uneditable fields (DateTimeField where auto_now or auto_now_add is True)
        """
        return [field.name for field in model._meta.get_fields() if field.name != "id" and not
                (field.get_internal_type() == "DateTimeField" and
                 (field.auto_now is True or field.auto_now_add is True)) and
                field.concrete and (not field.is_relation or field.one_to_one or
                                    (field.many_to_one and field.related_model))]

    #: Field types an icontains search can target. A search that reaches for a
    #: DateField or a ForeignKey id raises rather than returning nothing, so the
    #: list is a allowlist of text-ish types, never "everything that is not a pk".
    SEARCHABLE_INTERNAL_TYPES = (
        "CharField", "TextField", "SlugField", "EmailField", "URLField",
    )

    def get_searchable_field_names(self, model):
        """Concrete text-ish fields on this model, for the generated ?q= search."""
        return [
            field.name
            for field in model._meta.get_fields()
            if field.concrete
            and not field.is_relation
            and field.get_internal_type() in self.SEARCHABLE_INTERNAL_TYPES
        ]

    #: Field types with no business in a table cell: prose, blobs and
    #: structures. A JSONField renders as a Python repr and a TextField blows
    #: the row height out, and neither tells you which row you are looking at.
    LIST_EXCLUDED_INTERNAL_TYPES = (
        "TextField", "JSONField", "BinaryField", "FileField", "ImageField",
    )

    #: How many columns a list gets before it stops being scannable.
    MAX_LIST_FIELDS = 4

    #: How the generated pages ask before deleting. A typo here would
    #: otherwise fall through to the last branch and silently pick a mode
    #: nobody chose, so model_attributes refuses an unknown value.
    DELETE_CONFIRM_MODES = ("page", "inline", "dialog")

    #: Small, and out of the way of the control beside it. startr.style props.
    DEFAULT_DELETE_BUTTON_STYLE = "--size: 0.6rem; --p: 0.4rem; --ml: 1rem;"

    #: A base class name that marks a model append-only. Named, not imported:
    #: the base lives in the consuming project, never in this package.
    APPEND_ONLY_BASE_NAMES = ("AppendOnlyModel",)

    def list_field_rank(self, field):
        """Order columns by how much each one tells you about the row.

        A foreign key says what the row belongs to, which is the question a
        list answers most often. A choice says what state it is in. Then when,
        then yes-or-no, then the rest.
        """
        internal_type = field.get_internal_type()
        if field.is_relation:
            return 0
        if getattr(field, "choices", None):
            return 1
        if internal_type in ("DateField", "DateTimeField", "TimeField"):
            return 2
        if internal_type in ("BooleanField", "NullBooleanField"):
            return 3
        return 4

    def get_list_field_names(self, model):
        """Columns for the generated list page. A guess, and a correctable one.

        Before this, a list row was the bare object and so only as legible as
        the model's __str__. Widening __str__ instead is the tempting fix and
        the wrong one: the same string is what every ForeignKey dropdown, the
        admin changelist and every log line shows.

        The columns are written into the template literally, so a wrong guess
        costs one edit in one file — and since an existing file is never
        overwritten, that edit survives every later run.

        A correction that has to survive a REgeneration goes on the model
        instead::

            class Task(models.Model):
                class Startr:
                    list_fields = ["lead", "owner", "due_on", "done_at"]

        which is the form to reach for once anything makes re-rendering
        routine — changing STARTR_DELETE_CONFIRM re-renders every page.
        """
        chosen = getattr(getattr(model, "Startr", None), "list_fields", None)
        if chosen is not None:
            return [self.list_column(model, name) for name in chosen]

        wanted = set(self.get_field_names_for_model(model))
        candidates = []
        for position, field in enumerate(model._meta.get_fields()):
            if field.name not in wanted or not field.concrete:
                continue
            if field.get_internal_type() in self.LIST_EXCLUDED_INTERNAL_TYPES:
                continue
            candidates.append((self.list_field_rank(field), position, field))
        # Model field order breaks ties, so the result is stable across runs.
        candidates.sort(key=lambda entry: (entry[0], entry[1]))

        return [self.list_column(model, field.name)
                for _rank, _position, field in candidates[:self.MAX_LIST_FIELDS]]

    def list_column(self, model, name):
        """One column, described for the template that will unroll it."""
        field = model._meta.get_field(name)
        label = str(getattr(field, "verbose_name", None) or field.name).replace("_", " ")
        return {
            "name": field.name,
            "label": label[:1].upper() + label[1:],
            "internal_type": field.get_internal_type(),
            "is_relation": bool(field.is_relation),
            # blank as well as null: a CharField(blank=True, default="")
            # renders as nothing at all, which reads as a broken cell.
            "nullable": bool(getattr(field, "null", False) or getattr(field, "blank", False)),
        }

    def is_readonly(self, model):
        """Whether this model gets list and detail pages and nothing else.

        Three ways to say so, in order of precedence:

        * ``class Startr: readonly = True`` on the model. Canonical, because it
          sits next to the fields it describes.
        * a base class named in APPEND_ONLY_BASE_NAMES.
        * ``settings.STARTR_READONLY_MODELS``, holding "app_label.ModelName".

        Generating a CreateView for an append-only model is not a style
        preference. The form saves, the row appends, and the page lies about
        what happened.
        """
        options = getattr(model, "Startr", None)
        if options is not None and getattr(options, "readonly", False):
            return True
        for base in model.__mro__[1:]:
            if base.__name__ in self.APPEND_ONLY_BASE_NAMES:
                return True
        listed = getattr(settings, "STARTR_READONLY_MODELS", ()) or ()
        return "%s.%s" % (model._meta.app_label, model.__name__) in listed

    def create_directories(self, app):
        """
        If not already there, adds a directory for views, urls and templates.
        """
        for folder_name in ["views", "urls", "templates/%s" % app.label]:
            directory_path = "%s/%s" % (app.path, folder_name)
            if not os.path.exists(directory_path):
                os.makedirs(directory_path)

    def project_urls_path(self):
        """Locate the project's root urls.py from settings.ROOT_URLCONF.

        This used to be the literal string "/project/our_site/our_site/urls.py"
        — a path inside one specific container. Anywhere else the open() below
        raised FileNotFoundError, and because the call ran last it did so AFTER
        writing files. Returns None when the module cannot be located, which is
        a thing to report, never a thing to crash on.
        """
        root_urlconf = getattr(settings, "ROOT_URLCONF", None)
        if not root_urlconf:
            return None
        try:
            module = import_module(root_urlconf)
        except ImportError:
            return None
        path = getattr(module, "__file__", None)
        return path if path and os.path.exists(path) else None

    def ensure_debug_urls_in_project(self):
        """
        Check that the project's urls.py contains the necessary debug view lines.
        If not, instruct the user to add them. Never edits, never raises.
        """
        project_urls_path = self.project_urls_path()
        if project_urls_path is None:
            print("\033[93m[Startr] Could not locate the project's urls.py from "
                  "settings.ROOT_URLCONF; skipping the debug-URL check.\033[0m")
            return

        with open(project_urls_path, 'r') as f:
            content = f.read()

        required_lines = [
            "from django.urls import path, re_path, include",
            "from django.conf import settings",
            "from django_startr.views import debug_index",
            "handler404 = 'django_startr.views.debug_index'",
            "if settings.DEBUG:",
            "    urlpatterns += [",
            "        re_path(r'^.*$', debug_index),",
            "    ]",
        ]
        
        missing = [line for line in required_lines if line not in content]
        
        if missing:
            print("\033[93m[Startr] The following debug URL configuration lines are missing from your urls.py:\033[0m")
            for line in missing:
                print("  " + line)
            print("\033[93m[Startr] Please add them to your project's urls.py file.\033[0m")
            # Alternatively, if you wish to auto-update the file, you could prompt the user:
            # if input("Auto-add these lines? (y/N): ").lower() == "y":
            #     with open(project_urls_path, 'a') as f:
            #         f.write("\n\n# Startr Debug URLs\n" + "\n".join(required_lines) + "\n")
            #     print("Updated urls.py with debug URL configuration.")
        else:
            print("\033[92m[Startr] Your project's urls.py is already configured for debugging.\033[0m")
            print("\033[92m[Startr] If you encounter 404 errors, ensure that DEBUG is set to True in your settings.py.\033[0m")


    def create_init_files(self, app, model_names, models):
        """
        If not already there, creates a new __init__.py file in the views and urls directories.
        The init file imports from all of the files within the directory.
        """
        model_name_slugs = ["%s_views" % (self.camel_to_slug(model_name)) for model_name in model_names]
        model_names_dict = {self.camel_to_slug(model.__name__): self.camel_to_slug(self.model_name_plural(model)) for
                            model in models}
        for folder_name in ["views", "urls"]:
            file_path = "%s/%s/__init__.py" % (app.path, folder_name)
            template_path = "django_startr/__init__%s" % folder_name
            self.create_file_from_template(file_path, template_path, {
                "app_label": app.label,
                # The label and the import path are not the same thing for a
                # nested app: crm.record has the label "record", and an
                # include() built from the label is unimportable.
                "app_module": app.name,
                "model_name_slugs": model_name_slugs,
                "model_names_dict": model_names_dict,
            })

    def model_attributes(self, app, model):
        """
        Creates a dictionary of model attributes that will be used in the templates.
        """
        model_name = model.__name__
        model_name_plural = self.model_name_plural(model)
        slug_field = self.get_unique_slug_field_name(model)
        slug_field_name = slug_field.name if slug_field else "slug"
        lookup_field = slug_field_name if slug_field else "pk"
        model_name_slug = self.camel_to_slug(model_name)
        list_fields = self.get_list_field_names(model)
        related = [column['name'] for column in list_fields if column['is_relation']]
        return {
            'app_label': app.label,
            'app_path': app.path,
            'model': model,
            'model_name': model_name,
            'model_name_slug': model_name_slug,
            'model_name_plural': model_name_plural,
            'model_name_plural_slug': self.camel_to_slug(model_name_plural),
            'model_fields': self.get_field_names_for_model(model),
            'searchable_fields': self.get_searchable_field_names(model),
            'list_fields': list_fields,
            # Pre-quoted, so the stub writes .select_related([[ ... ]]) instead
            # of assembling a Python argument list inside a template.
            'list_related_args': ", ".join('"%s"' % name for name in related),
            'readonly': self.is_readonly(model),
            'delete_confirm': self.delete_confirm(),
            'delete_button_style': getattr(
                settings, 'STARTR_DELETE_BUTTON_STYLE',
                self.DEFAULT_DELETE_BUTTON_STYLE
            ),
            'slug_field': slug_field,
            'slug_field_name': slug_field_name,
            'lookup_field': lookup_field,
            # Two different bases, and conflating them is the easy mistake.
            # base_template is the per-model file the five pages extend;
            # project_base_template is the site shell that file extends. The
            # shell is NOT always "base.html" — reastate's is "_shell.html" —
            # so it comes from settings and never from a literal.
            'base_template': '%s/%s_base.html' % (app.label, model_name_slug),
            'project_base_template': getattr(
                settings, 'STARTR_BASE_TEMPLATE', 'base.html'
            ),
        }

    def delete_confirm(self):
        """Which second step the delete controls get. Never a silent default.

        settings.STARTR_DELETE_CONFIRM, one of DELETE_CONFIRM_MODES:

        ``page``    a link to the model's delete page, which the generator has
                    always written and nothing could reach. Works with
                    JavaScript off. The default.
        ``inline``  a <details> that opens the real form in place, so a long
                    list does not lose your position. No JavaScript either.
        ``dialog``  a real <dialog>, opened by django_startr's own static
                    file. The only mode that needs JavaScript, and the only
                    one with no confirmation when it is off.
        """
        mode = getattr(settings, 'STARTR_DELETE_CONFIRM', 'page')
        if mode not in self.DELETE_CONFIRM_MODES:
            raise ValueError(
                "STARTR_DELETE_CONFIRM is %r; expected one of %s"
                % (mode, ", ".join(self.DELETE_CONFIRM_MODES))
            )
        return mode

    def create_files_from_templates(self, model_attributes):
        """
        Determines the correct path to put each file and then calls create_file_from_template.
        """
        for folder_name in ["views", "urls"]:
            file_path = "%s/%s/%s_%s.py" % (model_attributes['app_path'], folder_name,
                                            model_attributes['model_name_slug'], folder_name)
            template_path = "django_startr/%s" % (folder_name)
            self.create_file_from_template(file_path, template_path, model_attributes)
        file_names = ["base", "list", "detail"]
        if not model_attributes['readonly']:
            file_names += ["create", "update", "delete"]
        for file_name in file_names:
            file_path = "%s/templates/%s/%s_%s.html" % (model_attributes['app_path'], model_attributes['app_label'],
                                                        model_attributes['model_name_slug'], file_name)
            template_path = "django_startr/%s.html" % (file_name)
            self.create_file_from_template(file_path, template_path, model_attributes)

    def create_file_from_template(self, file_path, template_path, context_variables):
        """
        Renders a stub through the META environment and writes it to file_path.

        Deliberately NOT django.template.loader.get_template. That resolves
        against the project's configured engines, so in a Jinja2-first project
        the stub could be picked up by the wrong engine — and the stubs are not
        the project's templates in the first place. metaenv owns them.

        An existing file is never overwritten. That contract is what makes this
        tool safe to run against an app someone has already hand-edited.
        """
        if os.path.exists(file_path):
            print("\033[91m" + file_path + " already exists.  Skipping." + "\033[0m")
            return
        stub_name = template_path.split("/")[-1]
        with open(file_path, 'w') as new_file:
            new_file.write(render_stub(stub_name, context_variables))
            print("\033[92m" + "successfully startrd " + file_path + "\033[0m")

    def remove_empty_startapp_files(self, app):
        """
        Removes 'empty' (less than or equal to 4 lines) views, admin, and tests files.
        """
        for file_name in ["views", "admin", "tests"]:
            file_path = "%s/%s.py" % (app.path, file_name)
            if os.path.exists(file_path):
                num_lines = sum(1 for _ in open(file_path))
                if num_lines <= 4:
                    os.remove(file_path)

    def camel_to_slug(self, name):
        """
        Helper method to convert a camel case string (e.g. PumpernickelBread) to a slug (e.g. pumpernickel_bread)
        """
        name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name).title().replace(" ", "").replace("_", "")
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        slug = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
        return slug

    def model_name_plural(self, model):
        """
        Returns the plural of the model name, adding an 's' if verbose_name_plural isn't set.
        """
        if isinstance(model._meta.verbose_name_plural, str):
            return model._meta.verbose_name_plural
        return "%ss" % model.__name__

    def get_unique_slug_field_name(self, model):
        """
        Determines if a model has exactly one unique SlugField. If so, returns it; otherwise, returns None.
        """
        slug_fields = []
        for field in model._meta.get_fields():
            if isinstance(field, SlugField) and field.unique:
                slug_fields.append(field)
        if len(slug_fields) == 1:
            return slug_fields[0]
        return None
