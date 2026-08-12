FROM node:22.19.0-bookworm-slim

WORKDIR /app

RUN groupadd --gid 10001 gateway \
    && useradd --uid 10001 --gid gateway --create-home --shell /usr/sbin/nologin gateway

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build \
    && npm prune --omit=dev \
    && mkdir -p /var/lib/dm-model-gateway \
    && chown -R gateway:gateway /app /var/lib/dm-model-gateway

ENV NODE_ENV=production

USER gateway

EXPOSE 3000

CMD ["node", "dist/src/index.js"]
