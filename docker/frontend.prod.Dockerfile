FROM node:20-alpine

WORKDIR /app/frontend

RUN corepack enable && corepack prepare pnpm@10.17.1 --activate

COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY frontend ./
COPY backend/apps /app/backend/apps

# Vite build-time env (beégetődik a bundle-be)
ARG VITE_API_URL=/api
ARG VITE_TENANT_DOMAIN=
ARG VITE_TURNSTILE_SITE_KEY=
ENV VITE_API_URL=$VITE_API_URL \
    VITE_TENANT_DOMAIN=$VITE_TENANT_DOMAIN \
    VITE_TURNSTILE_SITE_KEY=$VITE_TURNSTILE_SITE_KEY

RUN pnpm build

EXPOSE 4173

CMD ["sh", "-c", "pnpm preview --host 0.0.0.0 --port 4173"]
