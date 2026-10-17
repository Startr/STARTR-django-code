"""The app config. At startup it brands the Django admin.

The admin is named "Startr Admin" unless the project named it: a title set
on the site (``admin.site.site_header = ...``) or on an AdminSite subclass is
left alone, and ``STARTR_ADMIN_TITLE`` changes the default for one project.
The admin's sidebar goes, because the header carries the nav as tiers
(templates/admin/base_site.html); ``STARTR_ADMIN_NAV = False`` keeps Django's.
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
            if getattr(settings, "STARTR_ADMIN_NAV", True):
                admin.site.enable_nav_sidebar = False
