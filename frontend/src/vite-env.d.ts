/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
  readonly VITE_TENANT_DOMAIN?: string;
  readonly VITE_DEV_PROXY_TARGET?: string;
  readonly VITE_TURNSTILE_SITE_KEY?: string;
  readonly VITE_PLATFORM_ADMIN_MFA_REQUIRED?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
