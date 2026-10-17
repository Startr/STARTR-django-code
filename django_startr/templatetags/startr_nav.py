"""Template tags for the navs and the kit, for Django templates and the admin.

    {% load startr_nav %}
    {% startr_nav "dock" %}        the project's nav as a dock (or "tiers")
    {% startr_admin_nav %}         the admin's apps and models as tiers
    {% nav_icon item "--op-in-on:0" %}   one item's icon, extra props optional
    {% startr_style_url %}         the kit's stylesheet, settings.STARTR_STYLE_URL

A Jinja shell gets the same navs from the context processor as
``startr_nav_html("dock")``.
"""

from django import template
from django.conf import settings
from django.templatetags.static import static
from django.utils.safestring import mark_safe

from ..nav import admin_groups, admin_tail, icon_paths, render_nav

register = template.Library()

DEFAULT_STYLE_URL = "https://startr.style/style.css"


@register.simple_tag
def nav_icon(item, style=""):
    """A 22px stroke icon in currentColor. --h:22px, because the kit sizes every
    svg at 1.2em, which under a small label would shrink it to 12px."""
    extra = f" {style}" if style else ""
    return mark_safe(
        '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" '
        f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="--h:22px;{extra}">{icon_paths(item)}</svg>'
    )


@register.simple_tag(takes_context=True)
def startr_nav(context, kind="dock"):
    return render_nav(context.get("request"), kind)


@register.simple_tag(takes_context=True)
def startr_admin_nav(context):
    """Tiers from the admin's own ``available_apps``, permissions already applied."""
    request = context.get("request")
    path = getattr(request, "path", "") or ""
    groups = admin_groups(context.get("available_apps"), path)
    tail = admin_tail(path, groups, title=context.get("title"), subtitle=context.get("subtitle"),
                      obj=context.get("object") or context.get("original"))
    return render_nav(request, "tiers", items=[item for _, members in groups for item in members], groups=groups, tail=tail)


@register.simple_tag
def startr_style_url():
    """The kit's stylesheet. A full URL is used as is; anything else is a static path
    (a project that vendors the kit sets ``STARTR_STYLE_URL = "vendor/startr.style/style.css"``)."""
    url = getattr(settings, "STARTR_STYLE_URL", DEFAULT_STYLE_URL)
    return url if "://" in url or url.startswith("/") else static(url)
