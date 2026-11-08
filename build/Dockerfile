# syntax=docker/dockerfile:1
FROM debian:bookworm-slim AS builder

RUN DEBIAN_FRONTEND=noninteractive apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get dist-upgrade -y --no-install-recommends && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        build-essential ca-certificates curl dpkg-dev file patch \
        zlib1g-dev libssl-dev libpcre2-dev libxml2-dev libxslt1-dev libgd-dev libgeoip-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /workspace/build
COPY build/ /workspace/build/

RUN chmod +x build-deb.sh && OUT_DIR=/out ./build-deb.sh
