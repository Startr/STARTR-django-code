"""System checks for the admin skin. They run after setup, when the template
engines are built, which ``ready()`` cannot rely on.

``startr.W001``  the skin's ``admin/base_site.html`` is not the one served, so
                 the admin keeps Django's sidebar and the tiers never show
``startr.W002``  the engine that renders the admin lacks the ``request``
                 context processor, so no tier can mark the current page.
                 Django's ``admin.W411`` says the same about its own sidebar,
                 and the skin turns that sidebar off, so this check speaks.
"""
from django.apps import apps
from django.conf import settings
from django.core.checks import Tags, Warning, register

from .apps import SKIN_TEMPLATE, inspect_skin

REQUEST_PROCESSOR = "django.template.context_processors.request"


@register(Tags.templates)
def check_admin_skin(app_configs, **kwargs):
    if not apps.is_installed("django.contrib.admin"):
        return []
    served, detail = inspect_skin()
    if not served:
        return [Warning(
            f"django_startr's admin skin is inactive: {SKIN_TEMPLATE} comes from {detail}.",
            hint="List django_startr.admin_skin before django.contrib.admin in INSTALLED_APPS, "
                 f"or remove the {SKIN_TEMPLATE} your project overrides it with. Django's sidebar stays on.",
            id="startr.W001",
        )]
    if not getattr(settings, "STARTR_ADMIN_NAV", True):
        return []
    from django.template.loader import get_template

    engine = getattr(getattr(get_template(SKIN_TEMPLATE), "backend", None), "engine", None)
    if REQUEST_PROCESSOR not in (getattr(engine, "context_processors", None) or ()):
        return [Warning(
            f"The admin skin's tiers need {REQUEST_PROCESSOR} on the template engine that renders the admin.",
            hint=f"Add '{REQUEST_PROCESSOR}' to that DjangoTemplates engine's OPTIONS['context_processors'].",
            id="startr.W002",
        )]
    return []
