import { useEffect, useState } from "react";

import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import {
  activatePlatformAdminTenant,
  deactivatePlatformAdminTenant,
  fetchPlatformAdminStatistics,
  permanentlyDeletePlatformAdminTenant,
  restorePlatformAdminTenant,
} from "../api";
import { usePlatformAdminStore } from "../state";
import type { PlatformAdminStatisticsResponse, PlatformAdminStatisticsTenant } from "../types";
import PlatformAdminLayout from "./PlatformAdminLayout";

function formatDate(value: unknown): string {
  if (!value) return "-";
  const raw = String(value);
  const parsed = new Date(raw.includes("T") ? raw : `${raw}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return "-";
  return parsed.toLocaleDateString("hu-HU");
}

function formatNumber(value: unknown): string {
  return new Intl.NumberFormat("hu-HU").format(Number(value ?? 0));
}

function formatMoneyCents(value: unknown): string {
  const cents = Number(value ?? 0);
  return `${new Intl.NumberFormat("hu-HU", { maximumFractionDigits: 0 }).format(Math.round(cents / 100))} Ft`;
}

function StatCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-card)] p-6">
      <p className="text-sm text-[var(--color-muted)]">{label}</p>
      <p className="mt-3 text-3xl font-bold">{value}</p>
      {hint ? <p className="mt-2 text-xs text-[var(--color-muted)]">{hint}</p> : null}
    </div>
  );
}

type AiPageAction = "restore" | "activate" | "deactivate" | "permanent-delete";

type AiPageActionConfirmState = {
  action: AiPageAction;
  aiPage: PlatformAdminStatisticsTenant;
} | null;

function tenantStatusBadge(tenant: PlatformAdminStatisticsTenant) {
  const status = tenant.lifecycle_status ?? (tenant.is_active ? "active" : "inactive");
  if (status === "temporary_deleted") {
    return <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-800">Ideiglenesen törölt</span>;
  }
  if (tenant.is_active) {
    return <span className="rounded-full bg-green-100 px-3 py-1 text-xs font-semibold text-green-700">Aktív</span>;
  }
  return <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">Inaktív</span>;
}

function actionTitle(action: AiPageAction): string {
  if (action === "restore") return "NYZ Rating oldal visszaállítása";
  if (action === "activate") return "NYZ Rating oldal aktiválása";
  if (action === "deactivate") return "NYZ Rating oldal inaktiválása";
  return "NYZ Rating oldal végleges törlése";
}

function actionDescription(action: AiPageAction): string {
  if (action === "restore") return "A visszaállítás után a NYZ Rating oldal újra elérhető lesz a saját hostján.";
  if (action === "activate") {
    return "Az aktiválás után a tulajdonos újra be tud lépni. Ha van tartozás, csak a számlázás érhető el, amíg kiegyenlítik.";
  }
  if (action === "deactivate") {
    return "Az inaktiválás után a tulajdonos nem tud belépni, amíg újra nem aktiválod. A végleges törléshez előbb inaktiváld az oldalt.";
  }
  return "A végleges törlés eltávolítja a NYZ Rating oldal adatbázisát és nem vonható vissza.";
}

function actionErrorFallback(action: AiPageAction): string {
  if (action === "restore") return "Nem sikerült visszaállítani a NYZ Rating oldalt.";
  if (action === "activate") return "Nem sikerült aktiválni a NYZ Rating oldalt.";
  if (action === "deactivate") return "Nem sikerült inaktiválni a NYZ Rating oldalt.";
  return "Nem sikerült végleg törölni a NYZ Rating oldalt.";
}

export default function PlatformAdminDashboardPage() {
  const { token, user, loadingUser } = usePlatformAdminStore();
  const [statistics, setStatistics] = useState<PlatformAdminStatisticsResponse | null>(null);
  const [loadingTenants, setLoadingTenants] = useState(true);
  const [tenantError, setTenantError] = useState<string | null>(null);
  const [tenantActionPending, setTenantActionPending] = useState<number | null>(null);
  const [actionConfirm, setActionConfirm] = useState<AiPageActionConfirmState>(null);
  const [actionConfirmName, setActionConfirmName] = useState("");

  const loadStatistics = () => {
    setLoadingTenants(true);
    return fetchPlatformAdminStatistics()
      .then((result) => {
        setStatistics(result);
        setTenantError(null);
      })
      .catch((err) => {
        setTenantError(getApiErrorMessage(err) ?? "Nem sikerült betölteni a NYZ Rating oldalakat.");
      })
      .finally(() => setLoadingTenants(false));
  };

  useEffect(() => {
    if (loadingUser || !user || !token) return;
    let cancelled = false;
    setLoadingTenants(true);
    fetchPlatformAdminStatistics()
      .then((result) => {
        if (!cancelled) {
          setStatistics(result);
          setTenantError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) setTenantError(getApiErrorMessage(err) ?? "Nem sikerült betölteni a NYZ Rating oldalakat.");
      })
      .finally(() => {
        if (!cancelled) setLoadingTenants(false);
      });
    return () => {
      cancelled = true;
    };
  }, [loadingUser, token, user]);

  const summary = statistics?.summary;
  const tenants: PlatformAdminStatisticsTenant[] = statistics?.tenants ?? [];

  const openActionConfirm = (aiPage: PlatformAdminStatisticsTenant, action: AiPageAction) => {
    setActionConfirm({ aiPage, action });
    setActionConfirmName("");
  };

  const closeActionConfirm = () => {
    if (tenantActionPending != null) return;
    setActionConfirm(null);
    setActionConfirmName("");
  };

  const actionConfirmMatches = actionConfirmName.trim() === (actionConfirm?.aiPage.name ?? "");

  const handleConfirmAiPageAction = async () => {
    if (!actionConfirm || !actionConfirmMatches) return;
    const { aiPage, action } = actionConfirm;
    setTenantActionPending(aiPage.id);
    try {
      if (action === "restore") {
        await restorePlatformAdminTenant(aiPage.id, actionConfirmName.trim());
      } else if (action === "activate") {
        await activatePlatformAdminTenant(aiPage.id, actionConfirmName.trim());
      } else if (action === "deactivate") {
        await deactivatePlatformAdminTenant(aiPage.id, actionConfirmName.trim());
      } else {
        await permanentlyDeletePlatformAdminTenant(aiPage.id, actionConfirmName.trim());
      }
      setActionConfirm(null);
      setActionConfirmName("");
      await loadStatistics();
    } catch (err) {
      setTenantError(getApiErrorMessage(err) ?? actionErrorFallback(action));
    } finally {
      setTenantActionPending(null);
    }
  };

  return (
    <PlatformAdminLayout>
      <div className="space-y-6">
      <div>
        <p className="text-sm font-semibold uppercase tracking-[0.2em] text-[var(--color-muted)]">Monitoring</p>
        <h1 className="mt-2 text-3xl font-bold">Fő admin áttekintés</h1>
        <p className="mt-2 max-w-2xl text-[var(--color-muted)]">
          Itt kapnak majd helyet a platform szintű statisztikák, NYZ Rating oldalak és monitoring adatok.
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <StatCard label="Regisztrációk száma" value={loadingTenants ? "..." : formatNumber(summary?.tenants)} hint="NYZ Rating oldalak összesen" />
        <StatCard
          label="Havi kiküldött SMS"
          value={loadingTenants ? "..." : formatNumber(summary?.sms_sent_this_month)}
          hint="Aktuális periódus összesítése"
        />
        <StatCard
          label="Még felhasználható SMS"
          value={loadingTenants ? "..." : formatNumber(summary?.sms_remaining)}
          hint="Keret − kiküldött (addonnal együtt)"
        />
        <StatCard label="Adott évben befizetett összeg" value={loadingTenants ? "..." : formatMoneyCents(summary?.paid_this_year_cents)} />
        <StatCard label="Várható éves bevétel" value={loadingTenants ? "..." : formatMoneyCents(summary?.expected_annual_revenue_cents)} />
        <StatCard label="Várható átlagos havi bevétel" value={loadingTenants ? "..." : formatMoneyCents(summary?.expected_average_monthly_revenue_cents)} />
      </div>
      <div className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-card)] p-6">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold">Összes NYZ Rating oldal</h2>
            <p className="text-sm text-[var(--color-muted)]">Aktív, inaktív és ideiglenesen törölt NYZ Rating oldalak státusszal.</p>
          </div>
        </div>
        {tenantError ? <p className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{tenantError}</p> : null}
        {!tenantError && loadingTenants ? <p className="text-sm text-[var(--color-muted)]">NYZ Rating oldalak betöltése...</p> : null}
        {!tenantError && !loadingTenants && tenants.length === 0 ? (
          <p className="text-sm text-[var(--color-muted)]">Nincs NYZ Rating oldal.</p>
        ) : null}
        {!tenantError && tenants.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-[var(--color-border)] text-[var(--color-muted)]">
                <tr>
                  <th className="py-3 pr-4 font-medium">Oldal</th>
                  <th className="py-3 pr-4 font-medium">Csomag</th>
                  <th className="py-3 pr-4 font-medium">Fizetve</th>
                  <th className="w-16 py-3 pr-2 text-right font-medium" title="Havi kiküldött SMS">
                    SMS
                  </th>
                  <th className="w-16 py-3 pr-2 text-right font-medium" title="Még felhasználható SMS">
                    Maradék
                  </th>
                  <th className="py-3 pr-4 font-medium">Állapot</th>
                  <th className="py-3 pr-4 font-medium">Lemondás</th>
                  <th className="py-3 pr-4 font-medium text-right">Műveletek</th>
                </tr>
              </thead>
              <tbody>
                {tenants.map((tenant) => {
                  const temporaryDeleted = (tenant.lifecycle_status ?? "") === "temporary_deleted";
                  const inactive = !tenant.is_active && !temporaryDeleted;
                  const active = Boolean(tenant.is_active) && !temporaryDeleted;
                  const actionDisabled = tenantActionPending === tenant.id || tenantActionPending != null;
                  return (
                  <tr key={tenant.id} className="border-b border-[var(--color-border)]/60">
                    <td className="py-3 pr-4">
                      <div className="font-medium">{tenant.name}</div>
                      <div className="mt-0.5 font-mono text-xs text-[var(--color-muted)]">{tenant.slug}</div>
                    </td>
                    <td className="py-3 pr-4">
                      <div>
                        {tenant.package_name || tenant.package_code || "free"}
                        {` (${formatNumber(tenant.sms_monthly_max)})`}
                      </div>
                      <div className="mt-0.5 text-xs text-[var(--color-muted)]">
                        Létrehozva: {formatDate(tenant.created_at)}
                      </div>
                    </td>
                    <td className="py-3 pr-4">{formatDate(tenant.paid_until)}</td>
                    <td className="w-16 py-3 pr-2 text-right font-semibold tabular-nums">
                      {formatNumber(tenant.sms_sent_this_month)}
                    </td>
                    <td className="w-16 py-3 pr-2 text-right font-semibold tabular-nums">
                      {formatNumber(tenant.sms_remaining)}
                    </td>
                    <td className="py-3 pr-4">{tenantStatusBadge(tenant)}</td>
                    <td className="py-3 pr-4">
                      {tenant.cancellation_request?.requested_at
                        ? new Date(tenant.cancellation_request.requested_at).toLocaleString("hu-HU")
                        : "-"}
                    </td>
                    <td className="py-3 pr-4">
                      {temporaryDeleted ? (
                        <div className="flex justify-end gap-2">
                          <button
                            type="button"
                            disabled={actionDisabled}
                            onClick={() => openActionConfirm(tenant, "restore")}
                            className="rounded-lg border border-green-500 px-3 py-1.5 text-xs font-semibold text-green-700 hover:bg-green-50 disabled:opacity-50"
                          >
                            Visszaállítás
                          </button>
                          <button
                            type="button"
                            disabled={actionDisabled}
                            onClick={() => openActionConfirm(tenant, "permanent-delete")}
                            className="rounded-lg border border-red-500 px-3 py-1.5 text-xs font-semibold text-red-700 hover:bg-red-50 disabled:opacity-50"
                          >
                            Végleges törlés
                          </button>
                        </div>
                      ) : inactive ? (
                        <div className="flex justify-end gap-2">
                          <button
                            type="button"
                            disabled={actionDisabled}
                            onClick={() => openActionConfirm(tenant, "activate")}
                            className="rounded-lg border border-green-500 px-3 py-1.5 text-xs font-semibold text-green-700 hover:bg-green-50 disabled:opacity-50"
                          >
                            Aktiválás
                          </button>
                          <button
                            type="button"
                            disabled={actionDisabled}
                            onClick={() => openActionConfirm(tenant, "permanent-delete")}
                            className="rounded-lg border border-red-500 px-3 py-1.5 text-xs font-semibold text-red-700 hover:bg-red-50 disabled:opacity-50"
                          >
                            Törlés
                          </button>
                        </div>
                      ) : active ? (
                        <div className="flex justify-end">
                          <button
                            type="button"
                            disabled={actionDisabled}
                            onClick={() => openActionConfirm(tenant, "deactivate")}
                            className="rounded-lg border border-amber-500 px-3 py-1.5 text-xs font-semibold text-amber-800 hover:bg-amber-50 disabled:opacity-50"
                          >
                            Inaktiválás
                          </button>
                        </div>
                      ) : (
                        <span className="block text-right text-xs text-[var(--color-muted)]">-</span>
                      )}
                    </td>
                  </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
      {actionConfirm ? (
        <div className="fixed inset-0 z-[90] flex items-center justify-center bg-black/40 px-4" role="dialog" aria-modal="true">
          <div className="w-full max-w-lg rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-6 shadow-xl">
            <h2 className="text-xl font-semibold">{actionTitle(actionConfirm.action)}</h2>
            <p className="mt-2 text-sm text-[var(--color-muted)]">{actionDescription(actionConfirm.action)}</p>
            <div className="mt-4 rounded-xl bg-[var(--color-card-muted)] p-3 text-sm">
              <p>
                <span className="text-[var(--color-muted)]">NYZ Rating oldal neve: </span>
                <span className="font-semibold">{actionConfirm.aiPage.name}</span>
              </p>
              <p className="mt-1">
                <span className="text-[var(--color-muted)]">Host azonosító: </span>
                <span className="font-mono">{actionConfirm.aiPage.slug}</span>
              </p>
            </div>
            <label className="mt-4 block text-sm">
              <span className="text-[var(--color-muted)]">Megerősítéshez írd be pontosan a NYZ Rating oldal nevét.</span>
              <input
                value={actionConfirmName}
                onChange={(event) => setActionConfirmName(event.target.value)}
                className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2"
                autoComplete="off"
                autoFocus
              />
            </label>
            <div className="mt-5 flex justify-end gap-3">
              <button
                type="button"
                disabled={tenantActionPending != null}
                onClick={closeActionConfirm}
                className="rounded-lg border border-[var(--color-border)] px-4 py-2 text-sm font-medium hover:bg-[var(--color-border)]/25 disabled:opacity-50"
              >
                Mégse
              </button>
              <button
                type="button"
                disabled={!actionConfirmMatches || tenantActionPending != null}
                onClick={() => void handleConfirmAiPageAction()}
                className={`rounded-lg px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50 ${
                  actionConfirm.action === "permanent-delete"
                    ? "bg-red-600 hover:bg-red-700"
                    : actionConfirm.action === "deactivate"
                      ? "bg-amber-600 hover:bg-amber-700"
                      : "bg-green-600 hover:bg-green-700"
                }`}
              >
                {tenantActionPending != null ? "Folyamatban..." : "OK"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
      </div>
    </PlatformAdminLayout>
  );
}
