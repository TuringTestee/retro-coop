# syntax=docker/dockerfile:1
FROM rust:1.95.0-bookworm@sha256:6258907abe69656e41cd992e0b705cdcfabcbbe3db374f92ed2d47121282d4a1 AS core
WORKDIR /app
COPY spikes/d02 spikes/d02
COPY vendor/tetanes-core vendor/tetanes-core
RUN rustup target add wasm32-unknown-unknown && \
    cd spikes/d02 && cargo build --locked --release --lib --target wasm32-unknown-unknown

FROM node:24.13.1-bookworm-slim@sha256:a81a03dd965b4052269a57fac857004022b522a4bf06e7a739e25e18bce45af2 AS client-build
RUN apt-get update && apt-get install -y --no-install-recommends python3 ca-certificates && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY package.json package-lock.json tsconfig.json ./
COPY apps/client apps/client
COPY apps/coordinator/package.json apps/coordinator/package.json
COPY packages/contracts packages/contracts
COPY spikes/d02 spikes/d02
COPY scripts/foundation scripts/foundation
RUN npm ci
COPY --from=core /app/spikes/d02/target/wasm32-unknown-unknown/release/retro_coop_d02.wasm \
    /app/spikes/d02/target/wasm32-unknown-unknown/release/retro_coop_d02.wasm
RUN RETRO_COOP_PREBUILT_CORE=1 sh scripts/foundation/prepare.sh
ENV PUBLIC_COORDINATOR_URL=/coordinator
ENV PUBLIC_CATALOG_GAMES=super-tilt-bro-pal,from-below-1.0
RUN npm run build:staging

FROM nginx:1.29.3-alpine@sha256:b3c656d55d7ad751196f21b7fd2e8d4da9cb430e32f646adcf92441b72f82b14 AS edge
COPY deploy/aws-eb/nginx.conf /etc/nginx/nginx.conf
COPY --from=client-build /app/apps/client/dist /usr/share/nginx/html
USER 101:101
EXPOSE 8080
ENTRYPOINT ["nginx"]
CMD ["-g", "daemon off;"]

FROM node:24.13.1-bookworm-slim@sha256:a81a03dd965b4052269a57fac857004022b522a4bf06e7a739e25e18bce45af2 AS coordinator
WORKDIR /app
COPY package.json package-lock.json ./
COPY apps/coordinator/package.json apps/coordinator/package.json
COPY apps/client/package.json apps/client/package.json
COPY packages/contracts/package.json packages/contracts/package.json
RUN npm ci --omit=dev
COPY apps/coordinator/src apps/coordinator/src
COPY packages/contracts/src packages/contracts/src
RUN install -d -m 0700 -o node -g node /run/retro-coop-roms
USER 1000:1000
ENV COORDINATOR_STAGE=staging
ENV COORDINATOR_HOST=127.0.0.1
ENV COORDINATOR_PORT=8787
ENV COORDINATOR_TRUSTED_PROXIES=127.0.0.1
ENV COORDINATOR_ROM_DIR=/run/retro-coop-roms
ENV COORDINATOR_REQUIRE_CUSTOM_UPLOAD=1
ENV COORDINATOR_EMPTY_OFFERS=super-tilt-bro-pal,from-below-1.0
EXPOSE 8787
CMD ["node", "apps/coordinator/src/main.ts"]
