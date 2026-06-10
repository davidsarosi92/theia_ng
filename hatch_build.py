"""Custom Hatchling build hook.

Builds the Angular frontend and stages its dist into
``theia_ng/static/theia_ng/`` so it ends up inside the wheel. This runs
BEFORE the wheel is assembled, guaranteeing a complete artifact even if a
release pipeline forgets the frontend step.

The build is skipped (with a warning) if Node/npm is unavailable AND a
previously built bundle is already present — this keeps local `pip install -e .`
working for backend-only development.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

ROOT = Path(__file__).parent
FRONTEND = ROOT / "frontend"
DIST = FRONTEND / "dist" / "theia-ng" / "browser"  # Angular default output
TARGET = ROOT / "theia_ng" / "static" / "theia_ng"


class FrontendBuildHook(BuildHookInterface):
    PLUGIN_NAME = "custom"

    def initialize(self, version: str, build_data: dict) -> None:
        if shutil.which("npm") is None:
            if TARGET.exists() and any(TARGET.iterdir()):
                self.app.display_warning(
                    "npm not found; using already-built bundle in "
                    f"{TARGET.relative_to(ROOT)}"
                )
            else:
                # Don't hard-fail: this keeps `pip install -e .` working for
                # backend-only development without Node. The SPA view returns a
                # 501 with guidance until a bundle is present. Release CI always
                # builds the frontend explicitly before `python -m build`.
                self.app.display_warning(
                    "npm not found and no pre-built bundle present; shipping "
                    "without the SPA. Run `make frontend` to build it."
                )
            return

        self.app.display_info("Building Angular frontend (ng build)…")
        subprocess.run(["npm", "ci"], cwd=FRONTEND, check=True)
        subprocess.run(["npm", "run", "build"], cwd=FRONTEND, check=True)

        if TARGET.exists():
            shutil.rmtree(TARGET)
        TARGET.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(DIST, TARGET)
        self.app.display_info(f"Staged frontend bundle → {TARGET.relative_to(ROOT)}")
