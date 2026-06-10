"""Schema (IR) endpoints — the dynamic introspection surface.

* ``GET <prefix>api/schema/``            -> registry / nav payload
* ``GET <prefix>api/schema/<app.model>/`` -> full model descriptor (lazy)

These build the IR from the registry at runtime. Caching (per-deploy version
key, per-user) is a TODO — see the design notes; the StockCache pattern from the
iBar project is a good reference.
"""

from __future__ import annotations

from django.http import Http404, HttpRequest, JsonResponse

from theia_ng.introspection import build_model_detail, build_registry
from theia_ng.permissions import has_access
from theia_ng.registry import site


def _forbidden() -> JsonResponse:
    return JsonResponse({"detail": "Forbidden"}, status=403)


def schema_registry(request: HttpRequest) -> JsonResponse:
    if not has_access(request):
        return _forbidden()
    return JsonResponse(build_registry(site, request))


def schema_model(request: HttpRequest, model_key: str) -> JsonResponse:
    if not has_access(request):
        return _forbidden()

    match = site.get_model(model_key)
    if match is None:
        raise Http404(f"Model {model_key!r} is not registered")

    model, admin = match
    if not admin.has_view_permission(request):
        return _forbidden()
    return JsonResponse(build_model_detail(model, admin, request))
