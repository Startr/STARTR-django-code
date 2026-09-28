"""The app config. At startup it names the Django admin "Startr Admin".

A project that names its own admin keeps its name: a title set on the site
(``admin.site.site_header = ...``) or on an AdminSite subclass is left alone.
``STARTR_ADMIN_TITLE`` in settings changes the default for one project.
"""
from django.apps import AppConfig, apps
from django.conf import settings

DEFAULT_ADMIN_TITLE = "Startr Admin"


def brand_admin(site, title):
    """Give ``site`` the header and browser title ``title``, unless the project set its own.

    Identity, not equality: an untouched site still holds AdminSite's own lazy
    strings. The check reads through ``admin.site``, which is a LazyObject.
    """
    from django.contrib.admin import AdminSite

    for attr in ("site_header", "site_title"):
        if getattr(site, attr) is getattr(AdminSite, attr):
            setattr(site, attr, title)


class DjangoStartrConfig(AppConfig):
    name = "django_startr"

    def ready(self):
        if apps.is_installed("django.contrib.admin"):
            from django.contrib import admin

            brand_admin(admin.site, getattr(settings, "STARTR_ADMIN_TITLE", DEFAULT_ADMIN_TITLE))
