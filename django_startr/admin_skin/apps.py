"""The admin skin: the Django admin in the project's own look, automatically.

It ships two templates, ``admin/base_site.html`` and ``admin/login.html``. They
map the admin's CSS variables to startr.style's tokens and put the nav in the
header as tiers, in place of Django's sidebar.

Install order matters, and it is the reason this is an app of its own. A
template name is served from the first app in INSTALLED_APPS that has it. The
skin must come before ``django.contrib.admin`` to win ``admin/base_site.html``;
``django_startr`` must come after it, so its generic ``base.html`` and
``registration/*.html`` do not shadow the admin's own (a stray
``registration/logged_out.html`` turns Log out into a 500)::

    INSTALLED_APPS = [
        "django_startr.admin_skin",
        "django.contrib.admin",
        ...
        "django_startr",
    ]

Django's sidebar goes only when the skin is the template served, because the
tiers replace it and nothing else would. A project that overrides
``admin/base_site.html`` itself, or lists the skin after the admin, keeps its
sidebar, and the check ``startr.W001`` says why. ``STARTR_ADMIN_NAV = False``
keeps the sidebar too, tiers off. A custom ``AdminSite`` opts in with
``enable_nav_sidebar = False``: the header shows tiers exactly when the
sidebar is off, so a page never carries two navs or none.

The admin theme is the project's kit theme: light unless the project sets
``data-theme="dark"``. Django's own dark mode and theme toggle are left out
on purpose, since two themes would fight for the same variables.
"""
from django.apps import AppConfig, apps
from django.conf import settings

SKIN_TEMPLATE = "admin/base_site.html"


def inspect_skin():
    """``(served, detail)``: whether the admin would render this app's ``admin/base_site.html``.

    ``detail`` is the file Django found, or why it found none. Runs the real
    template lookup, so an override in a project's DIRS or an app listed ahead
    of the skin shows up as what it is.
    """
    from pathlib import Path

    from django.template.loader import get_template

    here = Path(__file__).resolve().parent / "templates"
    try:
        template = get_template(SKIN_TEMPLATE)
    except Exception as error:  # a broken override must not stop startup; the check reports it
        return False, f"{type(error).__name__}: {error}"
    name = str(template.origin.name)
    return Path(name).resolve().is_relative_to(here), name


def apply_skin(site):
    """Turn ``site``'s sidebar off, when the tiers will replace it.

    Leaves it alone with ``STARTR_ADMIN_NAV = False``, or when the skin's
    ``admin/base_site.html`` is not the one served (see ``checks.py``).
    """
    if getattr(settings, "STARTR_ADMIN_NAV", True) and inspect_skin()[0]:
        site.enable_nav_sidebar = False


class AdminSkinConfig(AppConfig):
    name = "django_startr.admin_skin"

    def ready(self):
        from . import checks  # noqa: F401  (registering the checks is the import)

        if apps.is_installed("django.contrib.admin"):
            from django.contrib import admin

            apply_skin(admin.site)
