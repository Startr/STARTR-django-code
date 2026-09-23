"""What a delete actually costs, counted before it happens.

"Are you sure?" is the confirmation people click through without reading,
because it names nothing. Django already knows exactly what a delete takes
with it — the same collector it runs a moment later — so the confirm step can
say it: this many rows go, this many references are cleared, or nothing can
happen at all because another table protects the row.

That last case is the one that used to 500. A PROTECT foreign key turns a
Delete button into a server error, and the page that offered the button had no
idea. Here it becomes a sentence and no Confirm button.
"""

from __future__ import annotations

from django.db import router
from django.db.models import QuerySet
from django.db.models.deletion import Collector, ProtectedError


def _plural(model, count, qualify=False):
    meta = model._meta
    name = meta.verbose_name if count == 1 else meta.verbose_name_plural
    if qualify:
        name = "%s %s" % (meta.app_label, name)
    return "%d %s" % (count, name)


def _phrases(pairs):
    """Format [(model, count), ...], qualifying any name that appears twice.

    Two apps with a model of the same name otherwise produce "1 link, 1 link",
    which tells the reader nothing about what is about to change.
    """
    seen = {}
    for model, _count in pairs:
        key = str(model._meta.verbose_name)
        seen[key] = seen.get(key, 0) + 1
    return [_plural(model, count, qualify=seen[str(model._meta.verbose_name)] > 1)
            for model, count in pairs]


def _counts(objects):
    """[(model, n), ...] for a mixed bag of instances, biggest first."""
    counts = {}
    for obj in objects:
        counts[type(obj)] = counts.get(type(obj), 0) + 1
    return sorted(counts.items(), key=lambda pair: -pair[1])


def summarise(obj):
    """Everything a delete of ``obj`` would touch.

    Returns a dict the confirm template renders directly:

    ``blocked``    True when a PROTECT relation refuses the delete outright
    ``protected``  ["12 leads", ...] — who is refusing, when blocked
    ``deletes``    ["1 lead", "3 threads", ...] — cascades, the row excluded
    ``clears``     ["2 actions", ...] — rows whose reference is set to null

    Never raises. A confirm page that cannot render is worse than one that
    says less: a failure to collect reports a blocked delete, and a failure to
    itemise a delete that collected fine reports no detail at all.
    """
    empty = {"blocked": False, "protected": [], "deletes": [], "clears": []}
    collector = Collector(using=router.db_for_write(type(obj), instance=obj))
    try:
        collector.collect([obj])
    except ProtectedError as exc:
        return dict(empty, blocked=True,
                    protected=_phrases(_counts(exc.protected_objects)))
    except Exception:
        return dict(empty, blocked=True)

    try:
        # Two places, and missing the second under-reports the damage. Django
        # moves any cascade it can clear in a single query into fast_deletes
        # and out of data, so a party that takes a lead, and the lead's tasks,
        # reports only the lead if you read data alone. Measured, not assumed.
        tally = {}
        for model, objects in collector.data.items():
            count = len(objects)
            if model is type(obj):
                # The row itself is not news. A self-referencing cascade is.
                count -= 1
            if count > 0:
                tally[model] = tally.get(model, 0) + count
        for queryset in getattr(collector, "fast_deletes", []):
            count = queryset.count()
            if count:
                tally[queryset.model] = tally.get(queryset.model, 0) + count

        deletes = sorted(tally.items(), key=lambda pair: -pair[1])

        # Distinct rows, not field updates. identity.Link reaches a party
        # through two fields, so counting updates reports one row as two —
        # and the values here are querysets as often as they are instances,
        # so len() on them counts querysets.
        cleared = {}
        for (field, _value), objects in getattr(collector, "field_updates", {}).items():
            pks = cleared.setdefault(field.model, set())
            for chunk in objects:
                if isinstance(chunk, QuerySet):
                    pks.update(chunk.values_list("pk", flat=True))
                else:
                    pks.add(chunk.pk)

        clears = sorted(((model, len(pks)) for model, pks in cleared.items() if pks),
                        key=lambda pair: -pair[1])
        return {"blocked": False, "protected": [],
                "deletes": _phrases(deletes), "clears": _phrases(clears)}
    except Exception:
        # Not protected, just not itemisable. A plain "Delete X?" is the old
        # behaviour and still correct; a confirm page that 500s is not.
        return dict(empty)


class DeleteSummaryMixin:
    """Puts ``delete_summary`` in front of the confirm step, and refuses the
    delete a PROTECT relation would refuse anyway.

    The refusal is checked twice on purpose. The template hides the Confirm
    button, and ``post`` checks again — a hidden button is a courtesy, not a
    guard, and the URL is still there to be typed.
    """

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["delete_summary"] = summarise(self.object)
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if summarise(self.object)["blocked"]:
            context = self.get_context_data(object=self.object)
            return self.render_to_response(context, status=409)
        return super().post(request, *args, **kwargs)
