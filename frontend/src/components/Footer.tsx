import { useTranslation } from "../i18n";

export default function Footer() {
  const { t } = useTranslation();
  return (
    <footer
      className="mt-auto w-full bg-[var(--color-background)] text-[var(--color-muted)] p-3 text-xs flex flex-col items-center justify-center gap-1 shrink-0 sm:flex-row sm:justify-between sm:gap-2"
      style={{ contentVisibility: "auto" }}
    >
      <span className="order-1 text-center lowercase sm:text-left">
        © {new Date().getFullYear()} – {t("footer.rights")}
      </span>
      <span className="order-2 font-medium">
        {t("app.name")}
      </span>
    </footer>
  );
}
