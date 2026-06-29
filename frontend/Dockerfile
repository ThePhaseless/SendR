FROM oven/bun:1.3.14@sha256:e10577f0db68676a7024391c6e5cb4b879ebd17188ab750cf10024a6d700e5c4 AS build

WORKDIR /app

COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

COPY . ./
RUN bunx ng build --configuration production

FROM nginxinc/nginx-unprivileged:1.31-alpine@sha256:a8d5564c3354241473c1e152d5dd3281ab4224edb61b23c291e0bfd9854687a1

USER root
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY docker-entrypoint.sh /custom-entrypoint.sh
RUN chmod +x /custom-entrypoint.sh
USER nginx

COPY --from=build /app/dist/frontend/browser /usr/share/nginx/html

EXPOSE 8080

ENTRYPOINT ["/custom-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
