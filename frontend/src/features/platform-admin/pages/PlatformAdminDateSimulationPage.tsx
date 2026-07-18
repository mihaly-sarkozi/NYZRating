import { useEffect, useMemo, useState } from "react";

import Alert from "../../../components/ui/Alert";
import Button from "../../../components/ui/Button";
import PageHeader from "../../../components/ui/PageHeader";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import {
  clearPlatformAdminDebugDate,
  fetchPlatformAdminDebugDate,
  fetchPlatformAdminTenants,
  setPlatformAdminSmsQuota,
  updatePlatformAdminDebugDate,
} from "../api";
import type { PlatformAdminTenant } from "../types";
import PlatformAdminLayout from "./PlatformAdminLayout";

export default function PlatformAdminDateSimulationPage() {
  const [debugDate, setDebugDate] = useState("");
  const [currentDate, setCurrentDate] = useState<string | null>(null);
  const [paymentSuccess, setPaymentSuccess] = useState(true);
  const [tenants, setTenants] = useState<PlatformAdminTenant[]>([]);
  const [smsTenantId, setSmsTenantId] = useState("");
  const [smsQuota, setSmsQuota] = useState("");
  const [saving, setSaving] = useState(false);
  const [savingSms, setSavingSms] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const fallbackCurrentDate = useMemo(() => new Date().toISOString().slice(0, 10), []);

  const loadDebugDate = async () => {
    setLoading(true);
    setError(null);
    try {
      const [dateResult, tenantResult] = await Promise.all([
        fetchPlatformAdminDebugDate(),
        fetchPlatformAdminTenants(),
      ]);
      setDebugDate(dateResult.simulated_date ?? "");
      setCurrentDate(dateResult.current_date ?? "");
      setPaymentSuccess((dateResult.payment_simulation_outcome ?? "success") !== "failed");
      setTenants(tenantResult);
      if (!smsTenantId && tenantResult.length > 0) {
        setSmsTenantId(String(tenantResult[0].id));
      }
    } catch (err) {
      setError(getApiErrorMessage(err) ?? "Nem sikerült betölteni a dátum szimulációt.");
      setCurrentDate(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadDebugDate();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- initial load only
  }, []);

  const saveDebugDate = async () => {
    setSaving(true);
    setError(null);
    setInfo(null);
    try {
      const outcome = paymentSuccess ? "success" : "failed";
      const result = await updatePlatformAdminDebugDate(debugDate || null, outcome);
      setDebugDate(result.simulated_date ?? "");
      setCurrentDate(result.current_date ?? "");
      setPaymentSuccess((result.payment_simulation_outcome ?? outcome) !== "failed");
      const outcomeLabel = paymentSuccess ? "sikeres" : "sikertelen";
      setInfo(
        debugDate
          ? `Dátum alkalmazva. Az aznapi esedékes fizetések ${outcomeLabel} kimenettel futottak.`
          : "Dátum törölve a mentéssel; a rendszer a valós dátumot használja."
      );
    } catch (err) {
      setError(getApiErrorMessage(err) ?? "Nem sikerült menteni a szimulált dátumot.");
    } finally {
      setSaving(false);
    }
  };

  const clearDebugDate = async () => {
    setSaving(true);
    setError(null);
    setInfo(null);
    try {
      const result = await clearPlatformAdminDebugDate();
      setDebugDate("");
      setCurrentDate(result.current_date ?? "");
      setInfo("A szimulált dátum törölve, a rendszer a valós dátumot használja.");
    } catch (err) {
      setError(getApiErrorMessage(err) ?? "Nem sikerült törölni a szimulált dátumot.");
    } finally {
      setSaving(false);
    }
  };

  const saveSmsQuota = async () => {
    const tenantId = Number(smsTenantId);
    const quota = Number(smsQuota);
    if (!Number.isFinite(tenantId) || tenantId <= 0) {
      setError("Válassz ki egy NYZ Rating oldalt.");
      return;
    }
    if (!Number.isFinite(quota) || !Number.isInteger(quota) || quota < 0) {
      setError("Az SMS keret csak nem negatív egész szám lehet.");
      return;
    }
    setSavingSms(true);
    setError(null);
    setInfo(null);
    try {
      const result = await setPlatformAdminSmsQuota(tenantId, quota);
      setInfo(
        `SMS keret mentve: ${result.name || result.slug} → ${result.remaining_total ?? result.sms_quota} SMS még felhasználható.`
      );
    } catch (err) {
      setError(getApiErrorMessage(err) ?? "Nem sikerült menteni az SMS keretet.");
    } finally {
      setSavingSms(false);
    }
  };

  return (
    <PlatformAdminLayout>
      <div className="mx-auto max-w-3xl space-y-6">
        <PageHeader
          eyebrow="Platform admin"
          title="Dátum szimuláció"
          description="A beállított dátum globálisan érvényes a számlázásra. Dátum alkalmazásakor lefut az esedékesség-ellenőrzés, és az aznapi fizetések a lenti beállítás szerint lesznek sikeresek vagy sikertelenek."
        />

        {error ? <Alert tone="error">{error}</Alert> : null}
        {info ? <Alert tone="success">{info}</Alert> : null}

        <div className="grid gap-4 md:grid-cols-2">
          <section className="app-surface space-y-4 p-6">
            <div>
              <h2 className="text-lg font-semibold">Fizetés kimenetele</h2>
              <p className="mt-1 text-sm text-[var(--color-muted)]">
                Ha a dátum alkalmazásakor aznap esedékes a fizetés, ez a beállítás dönt. Sikertelen fizetésnél a
                tulajdonos emailt kap; 30 nap után az oldal inaktívvá válik.
              </p>
            </div>

            <div className="flex items-center gap-3">
              <span className={`text-sm ${paymentSuccess ? "text-[var(--color-muted)]" : "font-semibold text-[var(--color-foreground)]"}`}>
                Sikertelen
              </span>
              <button
                type="button"
                role="switch"
                aria-checked={paymentSuccess}
                aria-label="Fizetés eredménye"
                disabled={saving || loading || savingSms}
                onClick={() => setPaymentSuccess((value) => !value)}
                className={`relative inline-flex h-8 w-14 shrink-0 cursor-pointer items-center rounded-full border transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
                  paymentSuccess ? "border-green-600 bg-green-600" : "border-red-500 bg-red-500"
                }`}
              >
                <span
                  className={`inline-block h-6 w-6 transform rounded-full bg-white shadow transition-transform ${
                    paymentSuccess ? "translate-x-7" : "translate-x-1"
                  }`}
                />
              </button>
              <span className={`text-sm ${paymentSuccess ? "font-semibold text-[var(--color-foreground)]" : "text-[var(--color-muted)]"}`}>
                Sikeres
              </span>
            </div>
          </section>

          <section className="app-surface space-y-4 p-6">
            <div>
              <h2 className="text-lg font-semibold">SMS keret szimuláció</h2>
              <p className="mt-1 text-sm text-[var(--color-muted)]">
                Válassz egy oldalt, add meg a hátralévő SMS keretet, majd tárold. A megadott érték lesz a még
                felhasználható SMS-ek száma.
              </p>
            </div>

            <label className="block">
              <span className="text-sm text-[var(--color-muted)]">NYZ Rating oldal</span>
              <select
                value={smsTenantId}
                onChange={(event) => setSmsTenantId(event.target.value)}
                disabled={loading || savingSms || tenants.length === 0}
                className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-input-bg)] px-3 py-2 text-sm text-[var(--color-foreground)]"
              >
                {tenants.length === 0 ? <option value="">Nincs elérhető oldal</option> : null}
                {tenants.map((tenant) => (
                  <option key={tenant.id} value={tenant.id}>
                    {tenant.name} ({tenant.slug})
                  </option>
                ))}
              </select>
            </label>

            <label className="block">
              <span className="text-sm text-[var(--color-muted)]">SMS keret (hátralévő)</span>
              <input
                type="number"
                min={0}
                step={1}
                value={smsQuota}
                onChange={(event) => setSmsQuota(event.target.value)}
                disabled={loading || savingSms}
                placeholder="pl. 10"
                className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-input-bg)] px-3 py-2 text-sm text-[var(--color-foreground)]"
              />
            </label>

            <Button
              type="button"
              size="sm"
              onClick={() => void saveSmsQuota()}
              disabled={loading || savingSms || !smsTenantId || smsQuota.trim() === ""}
            >
              {savingSms ? "Mentés..." : "Tárolás"}
            </Button>
          </section>
        </div>

        <section className="app-surface p-6">
          <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-sm font-medium text-[var(--color-muted)]">Aktuális rendszer dátum</p>
              <p className="mt-1 text-2xl font-semibold text-[var(--color-foreground)]">
                {loading ? "..." : currentDate || fallbackCurrentDate}
              </p>
              <p className="mt-2 text-sm text-[var(--color-muted)]">
                Üres dátummal a rendszer visszaáll a valós mai napra.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <input
                type="date"
                value={debugDate}
                onChange={(event) => setDebugDate(event.target.value)}
                className="rounded-lg border border-[var(--color-border)] bg-[var(--color-input-bg)] px-3 py-2 text-sm text-[var(--color-foreground)]"
              />
              <Button type="button" size="sm" onClick={saveDebugDate} disabled={saving || loading || savingSms}>
                {saving ? "Mentés..." : "Dátum alkalmazása"}
              </Button>
              <Button
                type="button"
                size="sm"
                variant="secondary"
                onClick={clearDebugDate}
                disabled={saving || loading || savingSms}
              >
                Visszaállítás
              </Button>
            </div>
          </div>
        </section>
      </div>
    </PlatformAdminLayout>
  );
}
