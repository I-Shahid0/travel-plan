# Meridian web (Next.js) — bun for install and build; node for the runtime.
# (@vercel/otel's fetch instrumentation corrupts response bodies under the bun
# runtime — empty JSON on every backend call — so the standalone server runs
# on node, same as the Playwright rig. See docs/handoff/phase-10.md.)
FROM oven/bun:1.3 AS deps

WORKDIR /app
COPY package.json bun.lock ./

# Install project dependencies with frozen lockfile for reproducible builds
RUN --mount=type=cache,target=/root/.bun/install/cache \
    bun install --no-save --frozen-lockfile


# Build stage in standalone mode
FROM oven/bun:1.3 AS builder

# Set working directory
WORKDIR /app

# Copy project dependencies from dependencies stage
COPY --from=deps /app/node_modules ./node_modules

# Copy application source code
COPY . .

ENV NEXT_TELEMETRY_DISABLED=1 \
    BETTER_AUTH_SECRET=meridian-build-placeholder \
    DATABASE_URL=postgresql://build:meridian-build-placeholder@localhost:5432/build

RUN bun run build

# Runtime stage — node, NOT bun: @vercel/otel's fetch instrumentation corrupts
# response bodies under the bun runtime (empty JSON on every backend call).
FROM node:22-alpine AS runtime

WORKDIR /app

ENV NODE_ENV=production \
    PORT=3001 \
    HOSTNAME=0.0.0.0 \
    NEXT_TELEMETRY_DISABLED=1

# Copy production assets. Line commented out because there is no public directory in the project. Could change in the future.
# COPY --from=builder --chown=node:node /app/public ./public

# Set the correct permission for prerender cache
RUN mkdir .next && chown node:node .next

# Automatically leverage output traces to reduce image size
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static

# Persists fetch cache generated during build so that cached responses are available immediately on startup.
COPY --from=builder --chown=node:node /app/.next/cache ./.next/cache

# Switch to non-root user for security best practices
USER node

EXPOSE 3001

# Start Next.js standalone server on node
CMD ["node", "server.js"]