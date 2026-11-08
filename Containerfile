# syntax=docker/dockerfile:1
FROM debian:bookworm-slim

LABEL maintainer="NGINX Docker Maintainers <docker-maint@nginx.com>"

ENV NGINX_VERSION=1.25.5 \
    NJS_VERSION=0.8.4 \
    NJS_RELEASE=3~bookworm \
    PKG_RELEASE=1~bookworm

COPY build/out/nginx_*.deb /tmp/

RUN set -eux; \
    groupadd --system --gid 101 nginx; \
    useradd --system --gid nginx --no-create-home --home /nonexistent \
        --comment "nginx user" --shell /bin/false --uid 101 nginx; \
    export DEBIAN_FRONTEND=noninteractive; \
    apt-get update; \
    # Upgrades base packages and resolves .deb dependencies (including libssl3 >= 3.0.14 for CVE-2024-4741)
    apt-get dist-upgrade -y --no-install-recommends; \
    apt-get install --no-install-recommends --no-install-suggests -y \
        /tmp/nginx_*.deb \
        gettext-base \
        ca-certificates; \
    mkdir -p /docker-entrypoint.d \
             /var/cache/nginx/client_temp /var/cache/nginx/proxy_temp \
             /var/cache/nginx/fastcgi_temp /var/cache/nginx/uwsgi_temp \
             /var/cache/nginx/scgi_temp; \
    chown -R nginx:nginx /var/cache/nginx; \
    ln -sf /dev/stdout /var/log/nginx/access.log; \
    ln -sf /dev/stderr /var/log/nginx/error.log; \
    rm -rf /tmp/nginx_*.deb /var/lib/apt/lists/*

COPY --chmod=0755 build/entrypoint/docker-entrypoint.sh /
COPY --chmod=0755 build/entrypoint/10-listen-on-ipv6-by-default.sh /docker-entrypoint.d
COPY --chmod=0755 build/entrypoint/15-local-resolvers.envsh /docker-entrypoint.d
COPY --chmod=0755 build/entrypoint/20-envsubst-on-templates.sh /docker-entrypoint.d
COPY --chmod=0755 build/entrypoint/30-tune-worker-processes.sh /docker-entrypoint.d

ENTRYPOINT ["/docker-entrypoint.sh"]
EXPOSE 80
STOPSIGNAL SIGQUIT
CMD ["nginx", "-g", "daemon off;"]
