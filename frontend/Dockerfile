# syntax=docker/dockerfile:1
# HELIOS COMMAND frontend: build with Node, serve static files with nginx.

# --- build stage ---
FROM node:22-alpine AS build
WORKDIR /app

# Install dependencies from the lockfile-free pinned package.json.
COPY package.json ./
RUN npm install

# Build the production bundle.
COPY . .
RUN npm run build

# --- runtime stage ---
FROM nginx:1.27-alpine AS runtime
# SPA routing: fall back to index.html so client-side routes work on refresh.
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
