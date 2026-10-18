"""The nav: every mounted list page, discovered from the URL resolver.

Exposing a generated model is two independent acts — mounting its urls module,
and linking to it from the site's shell. Nothing connects them, so the second
gets forgotten and a working page stays invisible. Trellis ran for months with
``/crm/tasks/`` answering 200 and no link to it anywhere.

This module removes the second act. Mount a model and it appears; unmount it
and it goes.

A project wires it as a context processor on whichever backend renders its
shell. Django's Jinja2 backend does run context processors — but only the ones
named in OPTIONS, since it adds none of its own::

    TEMPLATES = [{
        "BACKEND": "django.template.backends.jinja2.Jinja2",
        "OPTIONS": {
            "environment": "django_startr.jinja2env.environment",
            "context_processors": ["django_startr.nav.startr_nav"],
        },
    }]

The shell then writes three lines and never thinks about it again::

    {% for item in startr_nav %}
    <a href="{{ item.url }}">{{ item.label }}</a>
    {% endfor %}

The ready-made navs (``startr_nav_html("dock")`` and ``"tiers"``) need no
DjangoTemplates backend beside it: they render through an engine this module
owns, so a Jinja-only project, with or without the admin, gets them too.

Visibility
----------
An entry appears only where the viewer can use it. An authenticated user needs
``<app_label>.view_<model>`` — the admin's own permission machinery, not a
second one invented here.

An anonymous viewer sees every model entry, because a generated list view is
unauthenticated out of the box and hiding a page that answers 200 would be a
lie. A project that puts its lists behind login sets ``STARTR_NAV_ANON = False``
and anonymous viewers then see only the extras that ask no permission.

Settings, all optional:

``STARTR_NAV_ORDER``  slugs (or full route names) first, in this order; the
                      rest follow alphabetically by label
``STARTR_NAV_HIDE``   slugs never shown, whatever the permissions say
``STARTR_NAV_LABEL``  ``{slug or route name: label}``, overriding the derived
                      one. Key it by route name when two apps share a model
                      name.
``STARTR_NAV_EXTRA``  ``[(route_name, label[, requirement]), ...]``, for the
                      hand-written pages a resolver walk cannot recognise. The
                      requirement is a permission string, or one of
                      ``is_authenticated`` / ``is_staff`` / ``is_superuser``.
``STARTR_NAV_ANON``   default ``True``; ``False`` drops the anonymous pass
``STARTR_NAV_PRIMARY`` slugs (or route names) that belong in the main nav; see
                      below

Primary and secondary
---------------------
Mounting every model is the point, and nineteen links across the top of every
page is not. Each entry carries a ``primary`` flag so a shell can put the
handful people use inline and fold the rest into a disclosure — still one
click away, still discovered from the resolver, so a newly mounted model can
never go missing again.

What counts as primary, in order:

1. ``STARTR_NAV_PRIMARY`` when set. It decides, for model entries and extras
   alike.
2. Otherwise, if ``STARTR_NAV_ORDER`` is set: the entries it names, plus every
   extra. A project that bothered to order five pages has already said which
   five it cares about, so this needs no second list.
3. Otherwise everything is primary, which is what a project that sets neither
   already gets today.
"""

from __future__ import annotations

import functools
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.urls import NoReverseMatch, URLPattern, URLResolver, get_resolver, reverse

#: Both spellings. A hand-written route is as likely to be named "lead-list" as
#: the generator's "lead_list", and the nav has to find either — Trellis has one
#: of each, in the same urlconf.
LIST_SUFFIXES = ("_list", "-list")

#: Requirements an extra entry may ask for that are not Django permissions.
#: Anything else is passed to ``user.has_perm`` unchanged.
USER_FLAGS = {
    "is_authenticated": lambda user: bool(getattr(user, "is_authenticated", False)),
    "is_staff": lambda user: bool(getattr(user, "is_staff", False)),
    "is_superuser": lambda user: bool(getattr(user, "is_superuser", False)),
}

#: The resolver walk, memoised per urlconf. get_resolver() is itself cached by
#: Django, so without this the nav would re-walk every route on every request.
_ROUTE_CACHE: dict = {}


def reset_cache():
    """Forget the resolver walk. Tests and override_settings need this."""
    _ROUTE_CACHE.clear()


def _walk(resolver, namespaces, app_labels, out):
    """Collect every named route, carrying the namespace stack down with it.

    Recursion rather than resolver.reverse_dict, which only holds the routes of
    one namespace and so cannot see an included app at all.
    """
    for pattern in resolver.url_patterns:
        if isinstance(pattern, URLResolver):
            _walk(
                pattern,
                namespaces + [pattern.namespace] if pattern.namespace else namespaces,
                app_labels + [pattern.app_name] if pattern.app_name else app_labels,
                out,
            )
        elif isinstance(pattern, URLPattern) and pattern.name:
            out.append((namespaces, app_labels, pattern.name))


def list_slug(route_name):
    """"party_list" -> "party"; "lead-list" -> "lead"; anything else -> None."""
    for suffix in LIST_SUFFIXES:
        if route_name.endswith(suffix) and len(route_name) > len(suffix):
            return route_name[: -len(suffix)]
    return None


def model_for(app_label, slug):
    """The model a list route belongs to, or None when nothing matches.

    Matched on Django's own ``_meta.model_name`` — lowercase, no separators —
    so this needs no copy of the generator's camel_to_slug and cannot drift
    from it. "partial_lead" and "partiallead" both reach PartialLead.
    """
    if not app_label:
        return None
    try:
        config = apps.get_app_config(app_label)
    except LookupError:
        return None
    target = slug.replace("_", "").replace("-", "")
    for model in config.get_models():
        if model._meta.model_name == target:
            return model
    return None


def _discover():
    """Every list route in the project, with the model behind it."""
    key = getattr(settings, "ROOT_URLCONF", None)
    if key in _ROUTE_CACHE:
        return _ROUTE_CACHE[key]

    found = []
    _walk(get_resolver(), [], [], found)

    entries, seen = [], set()
    for namespaces, app_labels, route_name in found:
        slug = list_slug(route_name)
        if slug is None:
            continue
        full_name = ":".join(namespaces + [route_name])
        if full_name in seen:
            continue
        seen.add(full_name)
        app_label = app_labels[-1] if app_labels else (namespaces[-1] if namespaces else None)
        entries.append({
            "slug": slug,
            "name": full_name,
            "app_label": app_label,
            "model": model_for(app_label, slug),
        })

    _ROUTE_CACHE[key] = entries
    return entries


def _label(model, slug):
    """Sentence case, not title case: "Partial leads", never "Partial Leads"."""
    text = str(model._meta.verbose_name_plural) if model is not None else \
        slug.replace("_", " ").replace("-", " ")
    return text[:1].upper() + text[1:]


def _visible(user, model):
    """Whether this viewer should be offered the page."""
    if model is None:
        # An unrecognised list route. We cannot reason about it, and hiding a
        # page nobody asked us to hide is the worse mistake.
        return True
    if not getattr(user, "is_authenticated", False):
        return bool(getattr(settings, "STARTR_NAV_ANON", True))
    return user.has_perm("%s.view_%s" % (model._meta.app_label, model._meta.model_name))


def _disambiguate(items):
    """Two apps with a model of the same name produce two identical entries.

    Trellis has crm.Link and identity.Link, and a nav offering "Links" twice
    is no better than the hidden page this module exists to prevent. Colliding
    labels get their app's name in front; a label a project set by hand is left
    exactly as written.
    """
    counts = {}
    for item in items:
        counts[item["label"]] = counts.get(item["label"], 0) + 1
    for item in items:
        if counts[item["label"]] > 1 and not item["labelled"] and item["app_label"]:
            app = item["app_label"].replace("_", " ")
            item["label"] = "%s%s %s" % (app[:1].upper(), app[1:], item["label"].lower())


def _requirement_met(user, requirement):
    if not requirement:
        return True
    flag = USER_FLAGS.get(requirement)
    if flag is not None:
        return flag(user)
    return bool(user) and user.has_perm(requirement)


def nav_items(request):
    """The nav, in order, filtered to what this viewer can use."""
    user = getattr(request, "user", None)
    hide = set(getattr(settings, "STARTR_NAV_HIDE", ()) or ())
    labels = dict(getattr(settings, "STARTR_NAV_LABEL", {}) or {})
    order = list(getattr(settings, "STARTR_NAV_ORDER", ()) or ())

    primary = list(getattr(settings, "STARTR_NAV_PRIMARY", ()) or ())

    def is_primary(*keys):
        if primary:
            return any(key in primary for key in keys)
        if order:
            return any(key in order for key in keys)
        return True

    items = []
    for entry in _discover():
        if entry["slug"] in hide or entry["name"] in hide:
            continue
        if not _visible(user, entry["model"]):
            continue
        try:
            url = reverse(entry["name"])
        except NoReverseMatch:
            continue
        items.append({
            "name": entry["name"],
            "slug": entry["slug"],
            "url": url,
            "label": labels.get(entry["name"],
                                labels.get(entry["slug"],
                                           _label(entry["model"], entry["slug"]))),
            "labelled": entry["name"] in labels or entry["slug"] in labels,
            "app_label": entry["app_label"],
            "primary": is_primary(entry["slug"], entry["name"]),
        })

    _disambiguate(items)

    def rank(item):
        for key in (item["slug"], item["name"]):
            if key in order:
                return (0, order.index(key))
        return (1, 0)

    items.sort(key=lambda item: (rank(item), item["label"]))

    # Extras last and in declared order, because they are the project's own
    # pages and it already knows where it wants them.
    for extra in getattr(settings, "STARTR_NAV_EXTRA", ()) or ():
        name, label = extra[0], extra[1]
        requirement = extra[2] if len(extra) > 2 else None
        if name in hide or not _requirement_met(user, requirement):
            continue
        try:
            url = reverse(name)
        except NoReverseMatch:
            continue
        # An extra is the project's own page, named by hand in settings. With
        # only STARTR_NAV_ORDER set it is primary by default, because ordering
        # the model pages says nothing about these.
        items.append({
            "name": name, "slug": name, "url": url, "label": label,
            "primary": (name in primary) if primary else True,
        })

    return items


# ---------------------------------------------------------------------------
# The two navs the package renders from these items: a dock (a few pages in
# thumb reach, the rest under More) and tiers (groups on top, pages beneath).
# Both are automatic: groups are the project's apps, the phone dock is the
# first four primary pages, icons fall back to a generic glyph. Settings refine,
# never enable: STARTR_NAV_DOCK, STARTR_NAV_GROUPS, STARTR_NAV_ICONS.

#: 24x24 strokes in currentColor, keyed by slug (a model's list page) or route
#: name (an extra). A project adds or replaces entries with STARTR_NAV_ICONS.
#: "page" is the fallback, so a page is never dropped for lacking an icon.
DEFAULT_ICONS = {
    "lead": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    "task": '<path d="M9 11l3 3 8-8"/><path d="M20 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>',
    "thread": '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 21l1.9-5.4A8 8 0 1 1 21 12z"/>',
    "party": '<circle cx="9" cy="7" r="4"/><path d="M2 21a7 7 0 0 1 14 0M16 3.5a4 4 0 0 1 0 7.5M22 21a7 7 0 0 0-4-6.3"/>',
    "partial_lead": '<path d="M5 3h9l5 5v13H5z" stroke-dasharray="3 2.4"/><path d="M14 3v5h5"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    "group": '<circle cx="9" cy="7" r="4"/><path d="M2 21a7 7 0 0 1 14 0M16 3.5a4 4 0 0 1 0 7.5M22 21a7 7 0 0 0-4-6.3"/>',
    "ops:today": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M5 19l1.5-1.5M17.5 6.5L19 5"/>',
    "ops:team": '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M9 12l2 2 4-4"/>',
    "ops:scorecard": '<path d="M4 20V11M10 20V5M16 20v-6M2 20h20"/>',
    "crm:identity-queue": '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
    "crm:aiui-link": '<path d="M12 3l2 5.5L19.5 10 14 12l-2 5.5L10 12 4.5 10 10 8.5z"/>',
    "admin:index": '<path d="M4 7h10M18 7h2M4 17h4M12 17h8"/><circle cx="16" cy="7" r="2"/><circle cx="10" cy="17" r="2"/>',
    "more": '<circle cx="5" cy="12" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="19" cy="12" r="1.6"/>',
    "page": '<path d="M6 3h9l4 4v14H6z"/><path d="M15 3v4h4M9 12h6M9 16h6"/>',
}


def icon_paths(item):
    """The SVG inner markup for an item's icon: by slug, then route name, then the generic page."""
    icons = {**DEFAULT_ICONS, **(getattr(settings, "STARTR_NAV_ICONS", {}) or {})}
    return icons.get(item.get("slug")) or icons.get(item.get("name")) or icons["page"]


def with_current(items, path):
    """Mark ``current`` on every item whose URL is the longest prefix of ``path``.

    Every copy, not the first: a page can be rendered twice (dock and sheet,
    one shown per width), and the one on screen must carry the mark.
    """
    best = ""
    for item in items:
        url = item["url"]
        if path.startswith(url) and len(url) > len(best):
            best = url
    for item in items:
        item["current"] = bool(best) and item["url"] == best
    return items


def dock_items(items):
    """The pages in the phone dock, in dock order; ``dock_order`` is set on every item.

    ``STARTR_NAV_DOCK`` names them (slugs or route names). Unset, the first four
    primary pages: a project gets a working dock on install. A page in the dock
    is primary by definition, so a dock member that was not gets the flag: the
    bar draws primary pages only, and the sheet skips dock members, so without it
    the page would have no link anywhere.
    """
    keys = list(getattr(settings, "STARTR_NAV_DOCK", ()) or ())
    if keys:
        dock = [item for key in keys for item in items if item["slug"] == key or item["name"] == key]
    else:
        dock = [item for item in items if item["primary"]][:4]
    for item in dock:
        item["primary"] = True
    for item in items:
        item["dock_order"] = dock.index(item) if item in dock else 99
    return dock


def _app_name(item):
    label = item.get("app_label") or (item["name"].split(":")[0] if ":" in item.get("name", "") else None)
    if not label:
        return None
    try:
        return str(apps.get_app_config(label).verbose_name)
    except LookupError:
        return label.replace("_", " ").title()


def nav_groups(items):
    """``[(group label, [items])]``: the project's apps, in the items' order.

    ``STARTR_NAV_GROUPS`` (``{"Records": [slugs or route names]}``) names groups
    first; everything else falls to its app's verbose name, and a page with no
    app (a hand-written extra) to "Pages". Automatic for any project.
    """
    named = getattr(settings, "STARTR_NAV_GROUPS", {}) or {}
    groups, taken = [], set()
    for label, keys in named.items():
        members = [item for item in items if item["slug"] in keys or item["name"] in keys]
        taken.update(id(item) for item in members)
        if members:
            groups.append((label, members))
    by_app = {}
    for item in items:
        if id(item) in taken:
            continue
        by_app.setdefault(_app_name(item) or "Pages", []).append(item)
    groups.extend(by_app.items())
    return groups


def admin_groups(available_apps, path):
    """Tiers for the Django admin from its own app list: apps are groups, models are pages."""
    groups = []
    for app in available_apps or []:
        members = []
        for model in app.get("models", []):
            if not model.get("admin_url"):
                continue
            members.append({
                "label": str(model["name"]),
                "url": model["admin_url"],
                "slug": str(model.get("object_name", "")).lower(),
                "name": f"{app.get('app_label', '')}.{model.get('object_name', '')}",
                "primary": True,
            })
        if members:
            groups.append((str(app["name"]), members))
    with_current([item for _, members in groups for item in members], path)
    return groups


def admin_tail(path, groups, title=None, subtitle=None, obj=None):
    """The crumb a page below a change list adds to the tiers: the object, or the action.

    None on an index or a change list, where the tiers already say it all.
    Below a list (change, add, delete, history) the admin's own context names
    the page: ``subtitle`` (the object on a change form), ``object`` (delete,
    history) or ``title`` ("Add lead"). Delete and history name the action too.
    """
    lists = [item["url"] for _, members in groups for item in members]
    if not path or path in lists or not any(path.startswith(url) for url in lists):
        return None
    name = str(subtitle or obj or title or "").strip()
    if not name:
        return None
    for suffix, action in (("/delete/", "Delete"), ("/history/", "History")):
        if path.endswith(suffix) and (subtitle or obj):
            return f"{name} · {action}"
    return name


@functools.lru_cache(maxsize=1)
def _engine():
    """The package's own template engine, over its ``templates/`` folder.

    The navs are Django templates, and a project's TEMPLATES may hold only a
    Jinja2 backend, or a DjangoTemplates one without APP_DIRS. A private
    engine finds them either way. They read no context processor, so none is
    given; the two tag libraries they load are named here, not discovered.
    """
    from django.template import Engine

    return Engine(
        dirs=[str(Path(__file__).resolve().parent / "templates")],
        libraries={"startr_nav": "django_startr.templatetags.startr_nav", "static": "django.templatetags.static"},
        debug=settings.DEBUG,
    )


def render_nav(request, kind="dock", items=None, groups=None, tail=None):
    """The nav as HTML, from ``startr/nav_<kind>.html``: ``dock`` or ``tiers``.

    A Django template renders it, through the package's own engine, so the
    admin and a Jinja shell share one source whatever the project's TEMPLATES
    say; the context processor hands Jinja ``startr_nav_html``.
    """
    from django.template import Context

    path = getattr(request, "path", "") or ""
    if items is None:
        items = nav_items(request)
    with_current(items, path)
    context = {"items": items, "path": path, "kind": kind, "tail": tail, "more": {"slug": "more", "name": "more", "label": "More"}}
    if kind == "dock":
        dock = dock_items(items)
        context["dock"] = dock
        context["sheet"] = sorted((item for item in items if item not in dock), key=lambda item: not item["primary"])
    else:
        context["groups"] = groups if groups is not None else nav_groups(items)
        current = next((label for label, members in context["groups"] if any(m["current"] for m in members)), None)
        context["current_group"] = current or (context["groups"][0][0] if context["groups"] else None)
    return _engine().get_template(f"startr/nav_{kind}.html").render(Context(context))


def startr_nav(request):
    """Context processor. Puts ``startr_nav`` in front of every template, with the
    dock, the groups, the request path and ``startr_nav_html(kind)``."""
    items = with_current(nav_items(request), getattr(request, "path", "") or "")
    return {
        "startr_nav": items,
        "startr_nav_dock": dock_items(items),
        "startr_nav_groups": nav_groups(items),
        "startr_nav_path": getattr(request, "path", "") or "",
        "startr_nav_html": lambda kind="dock": render_nav(request, kind, items=items),
    }
