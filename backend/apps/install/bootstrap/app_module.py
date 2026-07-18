from __future__ import annotations

from core.kernel.interface import BaseAppModule, ModuleContext
from core.kernel.interface.app_conventions import module_key


class InstallAppModule(BaseAppModule):
    key = module_key("install")

    def register(self, container: ModuleContext) -> None:
        return None


def get_module() -> BaseAppModule:
    return InstallAppModule()


__all__ = ["InstallAppModule", "get_module"]
