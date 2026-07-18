import Button from "../../../components/ui/Button";

type PackageExpandBannerProps = {
  t: (key: string) => string;
  onOpen: () => void;
};

export default function PackageExpandBanner({ t, onOpen }: PackageExpandBannerProps) {
  return (
    <div className="mx-2 rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-4 text-sm leading-relaxed">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <p className="font-semibold text-[var(--color-foreground)]">{t("packages.bannerExpandModalTitle")}</p>
          <p className="mt-1 text-xs text-[var(--color-muted)]">{t("packages.smsExpandBannerNotice")}</p>
        </div>
        <Button type="button" onClick={onOpen} className="shrink-0 self-start sm:self-center">
          {t("packages.bannerExpandCta")}
        </Button>
      </div>
    </div>
  );
}
