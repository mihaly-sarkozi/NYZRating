# backend/apps/traffic/bootstrap/service_keys.py
# Feladat: A traffic app module.* service registry kulcsait definiálja.
# Sárközi Mihály - 2026.07.18

from core.kernel.interface.app_keys import module_service_key

TRAFFIC_SERVICE = module_service_key("traffic")

__all__ = ["TRAFFIC_SERVICE"]
