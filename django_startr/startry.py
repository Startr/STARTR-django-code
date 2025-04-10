from __future__ import print_function

import os
import re
import itertools

from django.db.models.fields import SlugField
from django.template.loader import get_template
from django.template import Context
from six import iteritems


class Startr(object):
    """
    Given a dictionary of apps and models, Startr will startr up a bunch of files that will help get your new app up
    and running quickly.
    """

    def startr(self, apps_and_models):
        """
        Iterates a dictionary of apps and models and creates all the necessary files to get up and running quickly.
        """
        for app_label, models_app in iteritems(apps_and_models):
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

        self.ensure_debug_urls_in_project("/project/our_site/our_site/urls.py")

    def get_field_names_for_model(self, model):
        """
        Returns fields other than id and uneditable fields (DateTimeField where auto_now or auto_now_add is True)
        """
        return [field.name for field in model._meta.get_fields() if field.name != "id" and not
                (field.get_internal_type() == "DateTimeField" and
                 (field.auto_now is True or field.auto_now_add is True)) and
                field.concrete and (not field.is_relation or field.one_to_one or
                                    (field.many_to_one and field.related_model))]

    def create_directories(self, app):
        """
        If not already there, adds a directory for views, urls and templates.
        """
        for folder_name in ["views", "urls", "templates/%s" % app.label]:
            directory_path = "%s/%s" % (app.path, folder_name)
            if not os.path.exists(directory_path):
                os.makedirs(directory_path)

    def ensure_debug_urls_in_project(self, project_urls_path):
        """
        Check that the project's urls.py contains the necessary debug view lines.
        If not, either auto-insert them or instruct the user to add them.
        """
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
            self.create_file_from_template(file_path, template_path, {"app_label": app.label,
                                                                      "model_name_slugs": model_name_slugs,
                                                                      "model_names_dict": model_names_dict
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
        return {
            'app_label': app.label,
            'app_path': app.path,
            'model': model,
            'model_name': model_name,
            'model_name_slug': self.camel_to_slug(model_name),
            'model_name_plural': model_name_plural,
            'model_name_plural_slug': self.camel_to_slug(model_name_plural),
            'model_fields': self.get_field_names_for_model(model),
            'slug_field': slug_field,
            'slug_field_name': slug_field_name,
            'lookup_field': lookup_field
        }

    def create_files_from_templates(self, model_attributes):
        """
        Determines the correct path to put each file and then calls create_file_from_template.
        """
        for folder_name in ["views", "urls"]:
            file_path = "%s/%s/%s_%s.py" % (model_attributes['app_path'], folder_name,
                                            model_attributes['model_name_slug'], folder_name)
            template_path = "django_startr/%s" % (folder_name)
            self.create_file_from_template(file_path, template_path, model_attributes)
        for file_name in ["base", "list", "detail", "create", "update", "delete"]:
            file_path = "%s/templates/%s/%s_%s.html" % (model_attributes['app_path'], model_attributes['app_label'],
                                                        model_attributes['model_name_slug'], file_name)
            template_path = "django_startr/%s.html" % (file_name)
            self.create_file_from_template(file_path, template_path, model_attributes)

    def create_file_from_template(self, file_path, template_path, context_variables):
        """
        Takes a template file and context variables and uses Django's render method to create a new file.
        """
        if os.path.exists(file_path):
            print("\033[91m" + file_path + " already exists.  Skipping." + "\033[0m")
            return
        with open(file_path, 'w') as new_file:
            new_file.write(get_template(template_path).render(context_variables))
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
