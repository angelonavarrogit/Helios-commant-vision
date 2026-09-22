# syntax=docker/dockerfile:1
# HELIOS COMMAND frontend: build with Node, serve static files with nginx.

# --- build stage ---
FROM node:22-alpine AS build
WORKDIR /app

# Install dependencies from the lockfile-free pinned package.json.
COPY package.json ./
RUN npm install

# Public API base URL, baked into the bundle at build time.
# EMPTY (default) = same-origin: the SPA calls "/api/..." and nginx proxies it
# to the backend (see nginx.conf). This is the production setup behind a reverse
# proxy / Cloudflare Tunnel. For local dev WITHOUT the proxy you may override
# with e.g. VITE_API_BASE_URL=http://localhost:8000.
ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

# Build the production bundle.
COPY . .
RUN npm run build

# --- runtime stage ---
FROM nginx:1.27-alpine AS runtime
# SPA routing: fall back to index.html so client-side routes work on refresh.
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
