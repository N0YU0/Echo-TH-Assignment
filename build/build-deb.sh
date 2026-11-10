#!/usr/bin/env bash
# Builds nginx 1.25.5 from upstream source with CVE-2024-7347 backported
# and packages the result as a Debian package (.deb).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="${OUT_DIR:-/out}"
WORK_DIR="/tmp/nginx-build"
PKG_ROOT="${WORK_DIR}/pkg"
NGINX_VERSION="1.25.5"
PKG_RELEASE="1~bookworm"
ARCH="$(dpkg --print-architecture)"

mkdir -p "${OUT_DIR}" "${WORK_DIR}"
cd "${WORK_DIR}"

echo "==> [1/4] Fetching nginx-${NGINX_VERSION} source..."
curl -fsSL "https://nginx.org/download/nginx-${NGINX_VERSION}.tar.gz" | tar -xz
cd "nginx-${NGINX_VERSION}"

echo "==> [2/4] Applying backport patches..."
for p in "${SCRIPT_DIR}"/patches/*.patch; do
    echo "    Applying $(basename "${p}")"
    patch -p1 < "${p}"
done
# Check if patch has been applied
grep -q "unordered mp4 stsc chunks" src/http/modules/ngx_http_mp4_module.c

echo "==> [3/4] Configuring and compiling nginx ${NGINX_VERSION}..."
./configure \
    --prefix=/etc/nginx \
    --sbin-path=/usr/sbin/nginx \
    --modules-path=/usr/lib/nginx/modules \
    --conf-path=/etc/nginx/nginx.conf \
    --error-log-path=/var/log/nginx/error.log \
    --http-log-path=/var/log/nginx/access.log \
    --pid-path=/var/run/nginx.pid \
    --lock-path=/var/run/nginx.lock \
    --http-client-body-temp-path=/var/cache/nginx/client_temp \
    --http-proxy-temp-path=/var/cache/nginx/proxy_temp \
    --http-fastcgi-temp-path=/var/cache/nginx/fastcgi_temp \
    --http-uwsgi-temp-path=/var/cache/nginx/uwsgi_temp \
    --http-scgi-temp-path=/var/cache/nginx/scgi_temp \
    --user=nginx --group=nginx \
    --with-compat --with-file-aio --with-threads \
    --with-http_addition_module --with-http_auth_request_module \
    --with-http_dav_module --with-http_flv_module \
    --with-http_gunzip_module --with-http_gzip_static_module \
    --with-http_mp4_module --with-http_random_index_module \
    --with-http_realip_module --with-http_secure_link_module \
    --with-http_slice_module --with-http_ssl_module \
    --with-http_stub_status_module --with-http_sub_module \
    --with-http_v2_module --with-http_v3_module \
    --with-mail --with-mail_ssl_module \
    --with-stream --with-stream_realip_module \
    --with-stream_ssl_module --with-stream_ssl_preread_module \
    --with-http_xslt_module=dynamic \
    --with-http_image_filter_module=dynamic \
    --with-http_geoip_module=dynamic \
    --with-stream_geoip_module=dynamic \
    --with-cc-opt="-g -O2 -fstack-protector-strong -Wformat -Werror=format-security -Wp,-D_FORTIFY_SOURCE=2 -fPIC" \
    --with-ld-opt="-Wl,-z,relro -Wl,-z,now -Wl,--as-needed -pie"

make -j"$(nproc)"

echo "==> [4/4] Packaging nginx_${NGINX_VERSION}-${PKG_RELEASE}_${ARCH}.deb..."
mkdir -p "${PKG_ROOT}/DEBIAN" \
         "${PKG_ROOT}/etc/nginx/conf.d" \
         "${PKG_ROOT}/usr/share/nginx/html" \
         "${PKG_ROOT}/var/log/nginx" \
         "${PKG_ROOT}/var/cache/nginx"

make install DESTDIR="${PKG_ROOT}"
strip --strip-unneeded "${PKG_ROOT}/usr/sbin/nginx" "${PKG_ROOT}/usr/lib/nginx/modules"/*.so
ln -s /usr/sbin/nginx "${PKG_ROOT}/usr/sbin/nginx-debug"

mv "${PKG_ROOT}/etc/nginx/html/"* "${PKG_ROOT}/usr/share/nginx/html/"
rmdir "${PKG_ROOT}/etc/nginx/html"
rm -f "${PKG_ROOT}/etc/nginx"/*.default

install -m 0644 "${SCRIPT_DIR}/config/nginx.conf" "${PKG_ROOT}/etc/nginx/nginx.conf"
install -m 0644 "${SCRIPT_DIR}/config/default.conf" "${PKG_ROOT}/etc/nginx/conf.d/default.conf"

find "${PKG_ROOT}/etc/nginx" -type f | sed "s|^${PKG_ROOT}||" > "${PKG_ROOT}/DEBIAN/conffiles"

cat > "${PKG_ROOT}/DEBIAN/control" <<EOF
Package: nginx
Version: ${NGINX_VERSION}-${PKG_RELEASE}
Section: httpd
Priority: optional
Architecture: ${ARCH}
Depends: libc6 (>= 2.34), libpcre2-8-0 (>= 10.22), libssl3 (>= 3.0.14), openssl (>= 3.0.14), zlib1g (>= 1:1.1.4), libxml2 (>= 2.9.14), libxslt1.1 (>= 1.1.35), libgd3 (>= 2.3.3), libgeoip1 (>= 1.6.12), tzdata
Maintainer: Echo Security Engineering <security@echo.local>
Description: nginx ${NGINX_VERSION} built from source with CVE-2024-7347 backported
EOF

dpkg-deb --build --root-owner-group "${PKG_ROOT}" "${OUT_DIR}/nginx_${NGINX_VERSION}-${PKG_RELEASE}_${ARCH}.deb"
