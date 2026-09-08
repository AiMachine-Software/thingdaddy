# ThingDaddy demo — ONE image that serves both the API and the pages.
# Build context is the REPO ROOT (see web/docker-compose.yml), because the app
# source lives in population/api and the pages live in web/public.
FROM node:22-alpine

WORKDIR /app

# Dependencies first, so a page edit does not re-run npm ci.
COPY population/api/package.json population/api/package-lock.json ./
RUN npm ci --omit=dev

# The API, unmodified apart from the 4-line opt-in static block in server.js.
COPY population/api/ ./

# The two demo pages. Same origin as the API => no CORS, no hardcoded host.
COPY web/public/ /app/public/

# PUBLIC_DIR is what switches static serving on. Without it server.js behaves
# exactly as it always has (API only).
ENV PUBLIC_DIR=/app/public \
    HOST=0.0.0.0 \
    PORT=8787 \
    NODE_ENV=production

EXPOSE 8787

CMD ["node", "server.js"]
