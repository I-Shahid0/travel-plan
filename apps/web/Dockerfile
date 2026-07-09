# Meridian web (Next.js) — bun for install, build, and runtime.
FROM oven/bun:1.3 AS deps

WORKDIR /app
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

FROM deps AS build
COPY . .
# Placeholders satisfy build-time page-data collection only; src/lib/env.ts
# rejects them on any real request, so runtime env must supply real values.
ENV NEXT_TELEMETRY_DISABLED=1 \
    BETTER_AUTH_SECRET=meridian-build-placeholder \
    DATABASE_URL=postgresql://build:meridian-build-placeholder@localhost:5432/build
# next/font downloads Google fonts at build time — needs network.
RUN bun run build

FROM oven/bun:1.3 AS runtime

WORKDIR /app
ENV NODE_ENV=production \
    PORT=3001 \
    HOSTNAME=0.0.0.0

COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static

EXPOSE 3001
CMD ["bun", "server.js"]
