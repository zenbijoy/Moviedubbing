"""
Third-Party NLE Plugin SDK & ABI Interface.

Extensible C/Python API contract for custom AI models, audio DSP filters, and custom exporters.
"""

from __future__ import annotations

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier


class PluginLoaderUnavailableError(RuntimeError):
    """Raised when no isolated plugin loader/runtime is configured."""


class PluginManifest(ContractModel):
    """Plugin metadata manifest."""

    plugin_id: Identifier
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    entry_point: str = Field(min_length=1)


class NLEPluginSDK:
    """
    Plugin SDK manager for loading third-party extensions.
    """

    def load_plugin(self, manifest: PluginManifest) -> bool:
        """
        Reject plugin loading until a real isolated runtime is configured.
        """
        del manifest
        raise PluginLoaderUnavailableError(
            "Plugin loading is unavailable: no ABI-compatible isolated plugin runtime is "
            "configured. No extension was loaded."
        )


__all__ = [
    "NLEPluginSDK",
    "PluginLoaderUnavailableError",
    "PluginManifest",
]
