FROM node:20-alpine AS build
WORKDIR /app
# Vite inlines `import.meta.env.VITE_*` at build time only. The build is
# triggered by docker compose with `args:` reading from .env, so the site
# key reaches the bundle without leaking anything secret (it's a public
# Turnstile site key, never the secret).
ARG VITE_TURNSTILE_SITE_KEY=""
ENV VITE_TURNSTILE_SITE_KEY=$VITE_TURNSTILE_SITE_KEY
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
