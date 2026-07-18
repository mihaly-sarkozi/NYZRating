// frontend/src/features/traffic/api/trafficService.ts
// Feladat: Traffic overview és SMS küldési napló API hívások.
// Sárközi Mihály - 2026.07.18

import api from "../../../api/axiosClient";
import type { TrafficOverview, TrafficSmsSendCreatePayload, TrafficSmsSendCreateResponse, TrafficSmsSendListResponse } from "../types/trafficTypes";

export async function fetchTrafficOverview(): Promise<TrafficOverview> {
  const res = await api.get("/traffic/overview");
  return res.data as TrafficOverview;
}

export async function fetchTrafficSmsSends(): Promise<TrafficSmsSendListResponse> {
  const res = await api.get("/traffic/sms-sends");
  return res.data as TrafficSmsSendListResponse;
}

export async function createTrafficSmsSend(payload: TrafficSmsSendCreatePayload): Promise<TrafficSmsSendCreateResponse> {
  const res = await api.post("/traffic/sms-sends", payload);
  return res.data as TrafficSmsSendCreateResponse;
}
