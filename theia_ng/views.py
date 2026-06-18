"""SPA entry point and bundle asset serving.

Everything lives under one configurable mount prefix. This view:

* serves real bundle files (JS/CSS/assets) when the path matches one, and
* otherwise returns ``index.html`` with two runtime injections so the SAME
  pre-built bundle works under ANY prefix without a rebuild:
    - ``<base href="{prefix}">`` so relative asset/router URLs resolve to the
      mount root regardless of client-side route depth, and
    - ``window.__THEIA_NG_CONFIG__`` with the API base + site config.
"""

from __future__ import annotations

import json
import mimetypes
import re
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, HttpRequest, HttpResponse

import theia_ng

_BUNDLE_DIR = (Path(theia_ng.__file__).parent / "static" / "theia_ng").resolve()
_INDEX = _BUNDLE_DIR / "index.html"


def _mount_prefix(request: HttpRequest, asset_path: str) -> str:
    """The mount root (with trailing slash), derived from the request path."""
    conf = getattr(settings, "THEIA_NG", {})
    if configured := conf.get("MOUNT_PREFIX"):
        return configured
    path = request.path
    return path[: len(path) - len(asset_path)] if asset_path else path


def _resolve_bundle_file(asset_path: str) -> Path | None:
    """Return the bundle file for ``asset_path`` if it exists (no traversal)."""
    if not asset_path:
        return None
    candidate = (_BUNDLE_DIR / asset_path).resolve()
    if _BUNDLE_DIR not in candidate.parents:
        return None  # path traversal guard
    return candidate if candidate.is_file() else None


def _render_index(request: HttpRequest, asset_path: str) -> HttpResponse:
    if not _INDEX.exists():
        return HttpResponse(
            "Theia NG bundle not found. Build the frontend (`make frontend`) "
            "or install a release wheel.",
            status=501,
            content_type="text/plain",
        )
    prefix = _mount_prefix(request, asset_path)
    conf = getattr(settings, "THEIA_NG", {})
    config = {
        "basePrefix": prefix,
        "apiBase": prefix.rstrip("/") + "/api/",
        "siteTitle": conf.get("SITE_TITLE", "Theia NG Admin"),
        "schemaVersion": "1.0",
        "version": theia_ng.__version__,
    }
    html = _INDEX.read_text(encoding="utf-8")

    # Point the (single) base href at the runtime mount prefix so relative asset
    # and router URLs resolve to the mount root at any route depth. Replace the
    # one baked in at build time; insert if absent.
    base_tag = f'<base href="{prefix}">'
    html, replaced = re.subn(r'<base href="[^"]*">', base_tag, html, count=1)
    if not replaced:
        html = html.replace("<head>", "<head>" + base_tag, 1)

    script = f"<script>window.__THEIA_NG_CONFIG__ = {json.dumps(config)};</script>"
    html = html.replace("</head>", script + "</head>", 1)
    return HttpResponse(html)


def spa(request: HttpRequest, asset_path: str = "") -> HttpResponse:
    bundle_file = _resolve_bundle_file(asset_path)
    if bundle_file is not None:
        content_type, _ = mimetypes.guess_type(str(bundle_file))
        return FileResponse(bundle_file.open("rb"), content_type=content_type)
    return _render_index(request, asset_path)
