import { useEffect, useId, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useTranslation, type Locale } from "../../../i18n";
import { trackLandingEvent } from "../analytics";
import "../landing.css";

const REGISTRATION_PATH = "/registration";
const LOCALES: Locale[] = ["hu", "en", "es"];

const HOW_STEPS = ["1", "2", "3", "4"] as const;
const BENEFITS = ["1", "2", "3", "4", "5", "6"] as const;
const AUDIENCES = ["salon", "beauty", "restaurant", "clinic", "auto", "local"] as const;
const PLANS = ["trial", "starter", "pro", "business"] as const;
const FAQS = ["1", "2", "3", "4", "5", "6"] as const;

function TrialCta({
  className,
  source,
  children,
}: {
  className?: string;
  source: string;
  children: ReactNode;
}) {
  return (
    <Link
      to={REGISTRATION_PATH}
      className={className}
      onClick={() => {
        trackLandingEvent("landing_trial_clicked", { source });
        trackLandingEvent("landing_demo_started", { source });
      }}
    >
      {children}
    </Link>
  );
}

function SectionHeading({
  eyebrow,
  title,
  lead,
  titleId,
}: {
  eyebrow?: string;
  title: string;
  lead?: string;
  titleId?: string;
}) {
  return (
    <div className="landing-section-head">
      {eyebrow ? <p className="landing-eyebrow">{eyebrow}</p> : null}
      <h2 id={titleId} className="landing-h2">
        {title}
      </h2>
      {lead ? <p className="landing-lead">{lead}</p> : null}
    </div>
  );
}

function FaqItem({ question, answer, id }: { question: string; answer: string; id: string }) {
  const [open, setOpen] = useState(false);
  const panelId = `${id}-panel`;

  return (
    <div className={`landing-faq-item${open ? " is-open" : ""}`}>
      <button
        type="button"
        className="landing-faq-q"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => {
          const next = !open;
          setOpen(next);
          if (next) trackLandingEvent("landing_faq_opened", { id });
        }}
      >
        <span>{question}</span>
        <span className="landing-faq-icon" aria-hidden>
          {open ? "−" : "+"}
        </span>
      </button>
      <div id={panelId} className="landing-faq-a" hidden={!open}>
        <p>{answer}</p>
      </div>
    </div>
  );
}

export default function LandingPage() {
  const { t, locale, setLocale } = useTranslation();
  const baseId = useId();
  const privacyHref = `/api/installer/privacy-policy.pdf?lang=${encodeURIComponent(locale)}`;

  useEffect(() => {
    document.title = `${t("landing.brand")} — ${t("landing.heroTitle")}`;
    return () => {
      document.title = "NYZRating";
    };
  }, [t, locale]);

  const scrollToPricing = () => {
    trackLandingEvent("landing_pricing_clicked", { source: "nav" });
    document.getElementById("landing-pricing")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div className="landing-root">
      <a href="#landing-main" className="landing-skip">
        {t("landing.skipToContent")}
      </a>

      <header className="landing-header">
        <div className="landing-header-inner">
          <a href="/" className="landing-logo" aria-label={t("landing.brand")}>
            <span className="landing-logo-mark" aria-hidden />
            <span className="landing-logo-text">{t("landing.brand")}</span>
          </a>
          <nav className="landing-nav" aria-label={t("landing.navLabel")}>
            <button type="button" className="landing-nav-link" onClick={scrollToPricing}>
              {t("landing.navPricing")}
            </button>
            <Link
              to="/login"
              className="landing-nav-link"
              onClick={() => trackLandingEvent("landing_login_clicked", { source: "header" })}
            >
              {t("landing.navLogin")}
            </Link>
          </nav>
          <TrialCta className="landing-btn landing-btn-primary landing-btn-sm landing-header-cta" source="header">
            {t("landing.ctaTrial")}
          </TrialCta>
          <div className="landing-lang" role="group" aria-label={t("landing.langLabel")}>
            {LOCALES.map((code) => (
              <button
                key={code}
                type="button"
                className={`landing-lang-btn${locale === code ? " is-active" : ""}`}
                onClick={() => setLocale(code)}
                aria-pressed={locale === code}
              >
                {code.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
      </header>

      <main id="landing-main">
        <section className="landing-hero" aria-labelledby="landing-hero-title">
          <div className="landing-hero-bg" aria-hidden />
          <div className="landing-hero-inner">
            <p className="landing-brand-hero">{t("landing.brand")}</p>
            <h1 id="landing-hero-title" className="landing-h1">
              {t("landing.heroTitle")}
            </h1>
            <p className="landing-hero-sub">{t("landing.heroSub")}</p>
            <div className="landing-hero-actions">
              <TrialCta className="landing-btn landing-btn-primary landing-btn-lg" source="hero">
                {t("landing.ctaTrial")}
              </TrialCta>
              <button type="button" className="landing-btn landing-btn-ghost landing-btn-lg" onClick={scrollToPricing}>
                {t("landing.ctaPricing")}
              </button>
            </div>
            <p className="landing-hero-note">{t("landing.heroNote")}</p>
          </div>
        </section>

        <section className="landing-section" aria-labelledby="landing-how-title">
          <div className="landing-container">
            <SectionHeading
              eyebrow={t("landing.howEyebrow")}
              title={t("landing.howTitle")}
              lead={t("landing.howLead")}
              titleId="landing-how-title"
            />
            <ol className="landing-steps">
              {HOW_STEPS.map((step, index) => (
                <li key={step} className="landing-step" style={{ animationDelay: `${index * 60}ms` }}>
                  <span className="landing-step-num">{step}</span>
                  <h3 className="landing-step-title">{t(`landing.howStep${step}Title`)}</h3>
                  <p className="landing-step-body">{t(`landing.howStep${step}Body`)}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="landing-section landing-section-alt" aria-labelledby="landing-benefits-title">
          <div className="landing-container">
            <SectionHeading
              eyebrow={t("landing.benefitsEyebrow")}
              title={t("landing.benefitsTitle")}
              lead={t("landing.benefitsLead")}
              titleId="landing-benefits-title"
            />
            <div className="landing-benefit-grid">
              {BENEFITS.map((n) => (
                <article key={n} className="landing-card">
                  <h3 className="landing-card-title">{t(`landing.benefit${n}Title`)}</h3>
                  <p className="landing-card-body">{t(`landing.benefit${n}Body`)}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="landing-section" aria-labelledby="landing-product-title">
          <div className="landing-container landing-product">
            <div className="landing-product-copy">
              <SectionHeading
                eyebrow={t("landing.productEyebrow")}
                title={t("landing.productTitle")}
                lead={t("landing.productLead")}
                titleId="landing-product-title"
              />
              <ul className="landing-product-points">
                <li>{t("landing.productPoint1")}</li>
                <li>{t("landing.productPoint2")}</li>
                <li>{t("landing.productPoint3")}</li>
              </ul>
            </div>
            <div className="landing-mockup" aria-hidden>
              <div className="landing-mockup-panel">
                <div className="landing-mockup-top">
                  <span />
                  <span />
                  <span />
                </div>
                <div className="landing-mockup-row">
                  <strong>{t("landing.mockStatLabel")}</strong>
                  <em>{t("landing.mockStatValue")}</em>
                </div>
                <div className="landing-mockup-bars">
                  <i style={{ width: "72%" }} />
                  <i style={{ width: "54%" }} />
                  <i style={{ width: "88%" }} />
                </div>
                <div className="landing-mockup-chip">{t("landing.mockChip")}</div>
              </div>
            </div>
          </div>
        </section>

        <section className="landing-section landing-section-alt" aria-labelledby="landing-sms-title">
          <div className="landing-container landing-sms-grid">
            <div>
              <SectionHeading
                eyebrow={t("landing.smsEyebrow")}
                title={t("landing.smsTitle")}
                lead={t("landing.smsLead")}
                titleId="landing-sms-title"
              />
            </div>
            <figure className="landing-sms-phone">
              <div className="landing-sms-bubble">
                <p className="landing-sms-from">{t("landing.smsFrom")}</p>
                <p className="landing-sms-body">{t("landing.smsBody")}</p>
                <p className="landing-sms-link">{t("landing.smsLink")}</p>
              </div>
              <figcaption className="landing-sms-caption">{t("landing.smsCaption")}</figcaption>
            </figure>
          </div>
        </section>

        <section className="landing-section" aria-labelledby="landing-audience-title">
          <div className="landing-container">
            <SectionHeading
              eyebrow={t("landing.audienceEyebrow")}
              title={t("landing.audienceTitle")}
              lead={t("landing.audienceLead")}
              titleId="landing-audience-title"
            />
            <div className="landing-audience-grid">
              {AUDIENCES.map((key) => (
                <article key={key} className="landing-audience-card">
                  <h3>{t(`landing.audience.${key}.title`)}</h3>
                  <p>{t(`landing.audience.${key}.body`)}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="landing-pricing" className="landing-section landing-section-alt" aria-labelledby="landing-pricing-title">
          <div className="landing-container">
            <SectionHeading
              eyebrow={t("landing.pricingEyebrow")}
              title={t("landing.pricingTitle")}
              lead={t("landing.pricingLead")}
              titleId="landing-pricing-title"
            />
            <div className="landing-pricing-grid">
              {PLANS.map((plan) => {
                const featured = plan === "pro";
                return (
                  <article key={plan} className={`landing-price-card${featured ? " is-featured" : ""}`}>
                    {featured ? <p className="landing-price-badge">{t("landing.pricingPopular")}</p> : null}
                    <h3 className="landing-price-name">{t(`landing.plan.${plan}.name`)}</h3>
                    <p className="landing-price-amount">
                      <span>{t(`landing.plan.${plan}.price`)}</span>
                      <small>{t(`landing.plan.${plan}.period`)}</small>
                    </p>
                    <p className="landing-price-sms">{t(`landing.plan.${plan}.sms`)}</p>
                    <ul className="landing-price-features">
                      <li>{t(`landing.plan.${plan}.f1`)}</li>
                      <li>{t(`landing.plan.${plan}.f2`)}</li>
                      <li>{t(`landing.plan.${plan}.f3`)}</li>
                    </ul>
                    <TrialCta
                      className={`landing-btn ${featured ? "landing-btn-primary" : "landing-btn-secondary"} landing-btn-block`}
                      source={`pricing_${plan}`}
                    >
                      {t("landing.ctaTrial")}
                    </TrialCta>
                  </article>
                );
              })}
            </div>
            <p className="landing-pricing-note">{t("landing.pricingNote")}</p>
          </div>
        </section>

        <section className="landing-section" aria-labelledby="landing-faq-title">
          <div className="landing-container landing-faq-wrap">
            <SectionHeading
              eyebrow={t("landing.faqEyebrow")}
              title={t("landing.faqTitle")}
              lead={t("landing.faqLead")}
              titleId="landing-faq-title"
            />
            <div className="landing-faq-list">
              {FAQS.map((n) => (
                <FaqItem
                  key={n}
                  id={`${baseId}-faq-${n}`}
                  question={t(`landing.faq${n}Q`)}
                  answer={t(`landing.faq${n}A`)}
                />
              ))}
            </div>
          </div>
        </section>

        <section className="landing-closing" aria-labelledby="landing-closing-title">
          <div className="landing-container landing-closing-inner">
            <h2 id="landing-closing-title" className="landing-h2 landing-closing-title">
              {t("landing.closingTitle")}
            </h2>
            <p className="landing-lead landing-closing-lead">{t("landing.closingLead")}</p>
            <TrialCta className="landing-btn landing-btn-primary landing-btn-lg" source="closing">
              {t("landing.ctaTrial")}
            </TrialCta>
          </div>
        </section>
      </main>

      <footer className="landing-footer">
        <div className="landing-container landing-footer-inner">
          <div>
            <p className="landing-footer-brand">{t("landing.brand")}</p>
            <p className="landing-footer-tag">{t("landing.footerTag")}</p>
          </div>
          <div className="landing-footer-links">
            <a href={privacyHref} target="_blank" rel="noreferrer">
              {t("landing.footerPrivacy")}
            </a>
            <a href={privacyHref} target="_blank" rel="noreferrer">
              {t("landing.footerLegal")}
            </a>
            <a href={`mailto:${t("landing.footerEmail")}`}>{t("landing.footerContact")}</a>
            <Link to="/login" onClick={() => trackLandingEvent("landing_login_clicked", { source: "footer" })}>
              {t("landing.navLogin")}
            </Link>
          </div>
          <p className="landing-footer-copy">
            © {new Date().getFullYear()} {t("landing.brand")}. {t("footer.rights")}
          </p>
        </div>
      </footer>
    </div>
  );
}
