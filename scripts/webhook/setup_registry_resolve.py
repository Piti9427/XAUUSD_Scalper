"""Resolve SetupRegistry persistence for webhook bridge (scenario 8)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from scripts.smc.setup_identity import SetupRegistry, load_setup_registry

DEFAULT_LIVE_SETUP_REGISTRY = "data/setup_registry.json"


def resolve_setup_registry(
    setup_registry_path: Optional[str],
    *,
    dry_run: bool,
    default_live_path: str = DEFAULT_LIVE_SETUP_REGISTRY,
) -> SetupRegistry:
    """
    Live bridge must persist terminal SETUP_IDs across restart.

    Dry-run tests default to an in-memory registry unless an explicit path is given.
    """
    if setup_registry_path:
        return load_setup_registry(Path(setup_registry_path))
    if not dry_run:
        return load_setup_registry(Path(default_live_path))
    return SetupRegistry()
