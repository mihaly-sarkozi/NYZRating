from __future__ import annotations

from apps.install.bootstrap.app_module import InstallAppModule as _InstallAppModule
from core.kernel.interface import BaseAppModule


class InstallAppModule(_InstallAppModule, BaseAppModule):
    pass


def get_module() -> BaseAppModule:
    return InstallAppModule()


__all__ = ["InstallAppModule", "get_module"]
