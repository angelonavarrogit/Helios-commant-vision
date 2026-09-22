# syntax=docker/dockerfile:1
# HELIOS COMMAND frontend: build with Node, serve static files with nginx.

# --- build stage ---
FROM node:22-alpine AS build
WORKDIR /app

# Install dependencies from the lockfile-free pinned package.json.
COPY package.json ./
RUN npm install

# Public base URL of the HELIOS API, baked into the bundle at build time.
# Defaults to localhost for dev; override in production (e.g. via
# docker compose build-arg) with your public API URL, e.g.
#   VITE_API_BASE_URL=https://api.helios.tudominio.com
ARG VITE_API_BASE_URL=http://localhost:8000
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
