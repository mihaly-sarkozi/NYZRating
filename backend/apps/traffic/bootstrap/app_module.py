from __future__ import annotations

from apps.traffic.bootstrap.service_keys import TRAFFIC_SERVICE
from apps.traffic.repositories.TrafficQuestionUsageRepository import TrafficQuestionUsageRepository
from apps.traffic.repositories.TrafficRepository import TrafficRepository
from apps.traffic.repositories.TrafficSmsSendRepository import TrafficSmsSendRepository
from apps.traffic.router.TrafficRouter import router as traffic_router
from apps.traffic.service.TrafficService import TrafficService
from core.kernel.interface import BaseAppModule, ModuleContext, RouteRegistration
from core.kernel.interface.app_conventions import module_key
from core.kernel.interface.keys import PLATFORM_CLOCK


class TrafficAppModule(BaseAppModule):
    key = module_key("traffic")

    def service_dependencies(self) -> tuple[str, ...]:
        return (PLATFORM_CLOCK,)

    def register(self, ctx: ModuleContext) -> None:
        service = TrafficService(
            repository=TrafficRepository(ctx.session_factory),
            question_usage_repository=TrafficQuestionUsageRepository(ctx.session_factory),
            sms_send_repository=TrafficSmsSendRepository(ctx.session_factory),
            clock=ctx.clock,
        )
        ctx.register_service(TRAFFIC_SERVICE, service)

    def routers(self) -> tuple[RouteRegistration, ...]:
        return (RouteRegistration(router=traffic_router, prefix="/api", tags=("platform-traffic",)),)

    def permissions(self) -> tuple[str, ...]:
        return ("traffic.read", "traffic.write")


def get_module() -> BaseAppModule:
    return TrafficAppModule()


__all__ = ["TrafficAppModule", "get_module"]
