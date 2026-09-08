# ThingDaddy — ONE image that serves the API and the built web app from one origin.
# Build context is the REPO ROOT (see deploy/docker-compose.yml).

# ---- stage 1: build the web app (apps/web -> /src/dist) ---------------------
FROM node:22-alpine AS web
WORKDIR /src
COPY package.json package-lock.json ./
COPY apps/web/package.json apps/web/
COPY apps/api/package.json apps/api/
RUN npm ci --ignore-scripts && npm rebuild esbuild
COPY apps/web/ apps/web/
# Same origin as the API: no VITE_API_BASE, no sub-path.
RUN npm run build

# ---- stage 2: runtime = the API + static dist -------------------------------
FROM node:22-alpine
WORKDIR /app
COPY apps/api/package.json apps/api/package-lock.json ./
RUN npm ci --omit=dev
COPY apps/api/ ./
COPY --from=web /src/dist /app/public

# PUBLIC_DIR switches static serving (and the SPA fallback) on in server.js.
ENV PUBLIC_DIR=/app/public \
    HOST=0.0.0.0 \
    PORT=8787 \
    NODE_ENV=production

EXPOSE 8787
CMD ["node", "server.js"]
