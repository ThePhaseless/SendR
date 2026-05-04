FROM oven/bun:1.3.11@sha256:0733e50325078969732ebe3b15ce4c4be5082f18c4ac1a0f0ca4839c2e4e42a7 AS build

WORKDIR /app

COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

COPY . ./
RUN bunx ng build --configuration production

FROM nginxinc/nginx-unprivileged:1.30-alpine@sha256:9d4ab2b70ec4b86e8576f783066d178d4725dc8c4b3bd060cb09f6d058ba9291

COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY docker-entrypoint.sh /custom-entrypoint.sh
RUN chmod +x /custom-entrypoint.sh
COPY --from=build /app/dist/frontend/browser /usr/share/nginx/html

ENV API_URL=http://api:8000

EXPOSE 8080

ENTRYPOINT ["/custom-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
