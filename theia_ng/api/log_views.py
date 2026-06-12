"""Read access to the Theia NG audit log.

``GET logs/`` returns the current user's own entries; a superuser sees everyone's
and may filter by ``?user=`` (username contains). Also filterable by ``?model=``
(model key) and ``?action=``, paginated like the other list endpoints.
"""

from __future__ import annotations

from django.core.paginator import Paginator
from django.http import HttpRequest, JsonResponse

from theia_ng.permissions import has_access


def _model_label(model_key: str) -> str:
    from theia_ng.registry import site

    resolved = site.get_model(model_key)
    return str(resolved[0]._meta.verbose_name) if resolved else model_key


def logs(request: HttpRequest) -> JsonResponse:
    if not has_access(request):
        return JsonResponse({"detail": "Forbidden"}, status=403)
    if request.method != "GET":
        return JsonResponse({"detail": "Method not allowed"}, status=405)

    from theia_ng.models import LogEntry

    user = request.user
    is_super = bool(getattr(user, "is_superuser", False))

    qs = LogEntry.objects.all()
    if is_super:
        # Superusers see everyone; optional username filter.
        if name := request.GET.get("user"):
            qs = qs.filter(username__icontains=name)
    else:
        # Everyone else sees only their own trail.
        qs = qs.filter(user=user)

    if model := request.GET.get("model"):
        qs = qs.filter(model_key=model)
    if action := request.GET.get("action"):
        qs = qs.filter(action=action)

    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get("page", 1))
    results = [
        {
            "id": e.id,
            "timestamp": e.timestamp.isoformat(),
            "username": e.username,
            "action": e.action,
            "model_key": e.model_key,
            "model_label": _model_label(e.model_key),
            "object_pk": e.object_pk,
            "object_repr": e.object_repr,
            "changes": e.changes,
        }
        for e in page
    ]
    return JsonResponse(
        {
            "count": paginator.count,
            "page": page.number,
            "num_pages": paginator.num_pages,
            "results": results,
            "is_superuser": is_super,
        }
    )
