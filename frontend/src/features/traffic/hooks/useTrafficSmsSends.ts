// frontend/src/features/traffic/hooks/useTrafficSmsSends.ts
// Feladat: SMS küldési napló listázása és létrehozása.
// Sárközi Mihály - 2026.07.18

import { useMutation, useQuery, useQueryClient, type UseQueryOptions } from "@tanstack/react-query";
import { queryKeys } from "../../../queryKeys";
import { useAuthStore } from "../../auth/state/authStore";
import { createTrafficSmsSend, fetchTrafficSmsSends } from "../api/trafficService";
import type { TrafficSmsSendCreatePayload, TrafficSmsSendListResponse } from "../types/trafficTypes";

export function useTrafficSmsSends(options?: Omit<UseQueryOptions<TrafficSmsSendListResponse>, "queryKey" | "queryFn">) {
  const user = useAuthStore((s) => s.user);
  return useQuery({
    queryKey: queryKeys.trafficSmsSends,
    queryFn: fetchTrafficSmsSends,
    enabled: user?.role === "owner" || user?.role === "admin",
    refetchOnMount: "always",
    ...options,
  });
}

export function useCreateTrafficSmsSend() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: TrafficSmsSendCreatePayload) => createTrafficSmsSend(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.trafficSmsSends });
      void queryClient.invalidateQueries({ queryKey: queryKeys.trafficOverview });
      void queryClient.invalidateQueries({ queryKey: queryKeys.billingOverview });
    },
  });
}
