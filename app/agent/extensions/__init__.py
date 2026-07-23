"""Disk-backed drop-in extension management primitives."""

from agent.extensions.discovery import build_diff, scan_extensions
from agent.extensions.models import (
    AppliedExtension,
    ExtensionChange,
    ExtensionDiff,
    ExtensionRegistry,
    ScanResult,
    ScannedExtension,
)
from agent.extensions.paths import ExtensionPaths, resolve_extension_paths
from agent.extensions.registry import (
    RegistryError,
    install_scanned_extension,
    load_registry,
    write_registry,
)

__all__ = [
    "AppliedExtension",
    "ExtensionChange",
    "ExtensionDiff",
    "ExtensionPaths",
    "ExtensionRegistry",
    "RegistryError",
    "ScanResult",
    "ScannedExtension",
    "build_diff",
    "install_scanned_extension",
    "load_registry",
    "resolve_extension_paths",
    "scan_extensions",
    "write_registry",
]
