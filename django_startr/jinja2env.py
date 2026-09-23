"""The RUNTIME layer: the Jinja2 environment generated templates render under.

A project points Django at this::

    TEMPLATES = [{
        "BACKEND": "django.template.backends.jinja2.Jinja2",
        "DIRS": [BASE_DIR / "myapp" / "templates"],
        "OPTIONS": {"environment": "django_startr.jinja2env.environment"},
    }]

Django's Jinja2 backend already injects ``request``, ``csrf_token`` and
``csrf_input`` into every render, so a generated template writes
``{{ csrf_input }}`` and needs nothing from us for CSRF. Verified by rendering,
not by reading the backend — see docs/decisions/.

Settings match AI-UI's ``pages/templates.py`` (``trim_blocks``,
``lstrip_blocks``) so a generated template is byte-portable into a Sprig.
"""

from __future__ import annotations

from django.templatetags.static import static as _static
from django.urls import reverse
from jinja2 import Environment

from .devnotes import DEV_GLOBALS


def url(name: str, *args, **kwargs) -> str:
    """Reverse a URL, taking route arguments positionally.

    Do NOT expose ``django.urls.reverse`` directly. Its signature is
    ``reverse(viewname, urlconf=None, args=None, kwargs=None)``, so a template
    writing the obvious ``{{ url('app:thing_detail', obj.pk) }}`` passes the pk
    as *urlconf* and Django raises

        ImproperlyConfigured: The included URLconf '1' does not appear to have
        any patterns in it

    which names neither the template nor the real mistake. Measured against a
    live project, not inferred. This wrapper is the whole fix.
    """
    return reverse(name, args=args or None, kwargs=kwargs or None)


def static(path: str) -> str:
    return _static(path)


def environment(**options) -> Environment:
    options.setdefault("trim_blocks", True)
    options.setdefault("lstrip_blocks", True)
    env = Environment(**options)
    env.globals.update({"static": static, "url": url})
    env.globals.update(DEV_GLOBALS)
    return env
