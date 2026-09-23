"""Dev notes: authoring marks visible in development, absent in production.

Ported from the 11ty system in WEB-Sage.is (``src/eleventy.config.js:52-81``,
spec at ``docs/ENVIRONMENT_TOGGLE.MD``). Same five names, so a person moving
between an 11ty site and a Django app does not learn a second vocabulary.

Two things change in the port, both deliberate.

**The polarity flips, and fails closed.** Sage.is tests
``NODE_ENV !== 'production'``, so forgetting the variable ships notes live.
Django's ``DEBUG`` defaults to ``False``, so silence is the default here and a
note can only appear where someone turned DEBUG on.

**No styling ships with this package.** startr.style already styles standard
HTML, so a note is a plain ``<aside>`` or ``<details>`` and carries no class of
its own for colour, no inline props, and no stylesheet. Where the framework does
not yet style an element the fix belongs upstream in startr.style core, not in a
private stylesheet here — four private stylesheets is the outcome that rule
exists to prevent.
"""

from __future__ import annotations

from django.conf import settings
from jinja2 import pass_context
from markupsafe import Markup, escape


def _on() -> bool:
    """Notes render only under DEBUG. Fails closed when DEBUG is unset."""
    return bool(getattr(settings, "DEBUG", False))


def devnote(note: str = "") -> Markup:
    """Inline mark. ``{{ devnote("check this") }}``"""
    if not _on() or not note:
        return Markup("")
    return Markup(f'<aside class="dev-note">{escape(note)}</aside>')


def _wrap(label: str, note: str, caller) -> Markup:
    body = caller() if caller is not None else ""
    return Markup(
        f'<details class="dev-note" open><summary>{escape(label)}'
        f'{": " + escape(note) if note else ""}</summary>{body}</details>'
    )


@pass_context
def todo(_ctx, note: str = "This section is under development", caller=None) -> Markup:
    """``{% call todo("wire the filter") %}…{% endcall %}`` — hidden in prod."""
    if not _on():
        return Markup("")
    return _wrap("TODO", note, caller)


@pass_context
def wip(_ctx, note: str = "Work in progress", caller=None) -> Markup:
    """Like ``todo``, but the CONTENT survives into production — only the
    wrapper is stripped. Matches the 11ty behaviour exactly."""
    if not _on():
        return Markup(caller() if caller is not None else "")
    return _wrap("WIP", note, caller)


@pass_context
def devonly(_ctx, caller=None) -> Markup:
    if not _on():
        return Markup("")
    return Markup(caller() if caller is not None else "")


@pass_context
def prodonly(_ctx, caller=None) -> Markup:
    if _on():
        return Markup("")
    return Markup(caller() if caller is not None else "")


DEV_GLOBALS = {
    "devnote": devnote,
    "todo": todo,
    "wip": wip,
    "devonly": devonly,
    "prodonly": prodonly,
}
