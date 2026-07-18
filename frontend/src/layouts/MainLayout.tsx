import { useState, useEffect, lazy, Suspense } from "react";
import { useLocation } from "react-router-dom";
import Navbar from "../components/Navbar";
import { useTranslation } from "../i18n";

const Footer = lazy(() => import("../components/Footer"));
import { Outlet } from "react-router-dom";

export default function MainLayout() {
  useTranslation();
  const [showFooter, setShowFooter] = useState(false);
  const location = useLocation();
  const isFullHeight = location.pathname === "/onboarding/train";

  useEffect(() => {
    const id = requestAnimationFrame(() => {
      requestAnimationFrame(() => setShowFooter(true));
    });
    return () => cancelAnimationFrame(id);
  }, []);

  return (
    <div
      className={`flex flex-col bg-[var(--color-background)] text-[var(--color-foreground)] ${
        isFullHeight ? "h-screen overflow-hidden" : "min-h-screen"
      }`}
    >
      <Navbar topOffsetClassName="top-0" />

      <main
        className={`pt-20 flex-1 min-h-0 flex flex-col ${isFullHeight ? "overflow-hidden" : ""}`}
        aria-label="Fő tartalom"
      >
        <Outlet />
      </main>

      {showFooter && (
        <Suspense fallback={null}>
          <Footer />
        </Suspense>
      )}
    </div>
  );
}
