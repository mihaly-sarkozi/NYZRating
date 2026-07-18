// Feladat: A traffic frontend API response típusait tartalmazza.

export type TrafficCatalogEntry = {
  entry_type: string;
  code: string;
  name: string;
  currency: string;
  price_cents: number;
  price: number;
  included: Record<string, unknown>;
  metadata: Record<string, unknown>;
};

export type TrafficOverview = {
  current_period_key: string;
  current_period_start_iso: string;
  current_period_end_iso: string;
  catalog: TrafficCatalogEntry[];
  subscription: Record<string, unknown>;
  limits: Record<string, unknown>;
  usage: Record<string, unknown>;
};

export type TrafficSmsSendItem = {
  id: number;
  recipient_name: string;
  phone: string;
  scheduled_at: string;
  status: string;
  period_key: string;
  created_at: string;
};

export type TrafficSmsSendListResponse = {
  items: TrafficSmsSendItem[];
  remaining_total: number;
  available_total: number;
  used_total: number;
};

export type TrafficSmsSendCreatePayload = {
  recipient_name: string;
  phone: string;
  scheduled_at: string;
};

export type TrafficSmsSendCreateResponse = {
  item: TrafficSmsSendItem;
  remaining_total: number;
  available_total: number;
  used_total: number;
};
