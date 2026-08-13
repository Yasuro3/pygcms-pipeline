"""Shared Playwright browser launcher with an optional system-Chromium fallback."""
from __future__ import annotations

import os
import shutil
from typing import Any


def chromium_launch_kwargs() -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "headless": True,
        "args": ["--no-sandbox", "--disable-dev-shm-usage"],
    }
    explicit = os.environ.get("PYGCMS_CHROMIUM", "").strip()
    system = explicit or shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
    if system:
        kwargs["executable_path"] = system
    return kwargs


def launch_chromium(playwright: Any):
    return playwright.chromium.launch(**chromium_launch_kwargs())
