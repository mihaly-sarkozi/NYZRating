import { Navigate, useLocation } from "react-router-dom";

const LEGACY_MAP: Record<string, string> = {
  "/demo": "/install",
  "/demo-login": "/install-login",
  "/demo-expired": "/install-expired",
  "/demo-email-sent": "/install-email-sent",
};

export default function LegacyDemoRedirect() {
  const location = useLocation();
  const basePath = location.pathname.replace(/\/+$/, "") || "/";
  const target = LEGACY_MAP[basePath] || "/install";
  return <Navigate to={`${target}${location.search}${location.hash}`} replace />;
}
