# ---- build stage ----
FROM node:20-slim AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund
COPY tsconfig.json vite.config.ts index.html ./
COPY src ./src
RUN npm run build

# ---- runtime stage ----
FROM nginx:1.27-alpine AS runtime
ENV WEB_LISTEN_PORT=8080
RUN apk add --no-cache gettext
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
# Shell form so the port env var is expanded at container run time.
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=5 \
    CMD wget -qO- "http://127.0.0.1:${WEB_LISTEN_PORT}/healthz" >/dev/null 2>&1 || exit 1
CMD ["/bin/sh", "-c", "envsubst '$$WEB_LISTEN_PORT' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf && exec nginx -g 'daemon off;'"]
