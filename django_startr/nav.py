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


def startr_nav(request):
    """Context processor. Puts ``startr_nav`` in front of every template."""
    return {"startr_nav": nav_items(request)}
