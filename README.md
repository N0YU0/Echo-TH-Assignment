# Echo Take-Home Assignment — Build It, Patch It, Ship It

A drop-in, source-built replacement for `nginx:1.25-bookworm` compiled from upstream source on `debian:bookworm-slim`, eliminating **`CVE-2024-4741`** via a **dependency version bump (`libssl3` / `openssl`)** and **`CVE-2024-7347`** via an **upstream commit backport patch (`ngx_http_mp4_module.c`)** onto `nginx 1.25.5`, verified with **OpenVEX (`vex.openvex.json`)** and an **automated differential compatibility test suite (`test/compat_test.py`)**.

---

## Repository Structure

```text
.
├── build/
│   ├── Dockerfile                     # Clean-room source builder (debian:bookworm-slim)
│   ├── build-deb.sh                   # Fetches upstream nginx 1.25.5, applies CVE-2024-7347.patch, builds .deb
│   ├── out/
│   │   └── nginx_1.25.5-1~bookworm_amd64.deb   # Compiled nginx 1.25.5 .deb package
│   ├── patches/
│   │   └── CVE-2024-7347.patch        # Backport: MP4 stsc integer overflow / buffer over-read fix
│   ├── config/
│   │   ├── nginx.conf                 # Upstream-identical /etc/nginx/nginx.conf
│   │   └── default.conf               # Upstream-identical /etc/nginx/conf.d/default.conf
│   └── entrypoint/
│       ├── docker-entrypoint.sh       # Upstream-identical entrypoint dispatcher
│       ├── 10-listen-on-ipv6-by-default.sh
│       ├── 15-local-resolvers.envsh
│       ├── 20-envsubst-on-templates.sh
│       └── 30-tune-worker-processes.sh
├── Containerfile                      # Upgrades libssl3 (CVE-2024-4741) & installs compiled nginx .deb
├── Makefile                           # Single-command build, scan, and compatibility test orchestration
├── vex.openvex.json                   # OpenVEX v0.2.0 attestation for backport-patched CVE-2024-7347
├── baseline-trivy.txt                 # Baseline Trivy scan of nginx:1.25-bookworm
├── baseline-grype.txt                 # Baseline Grype scan of nginx:1.25-bookworm
├── scans/                             # Full baseline, patched, and VEX-filtered Trivy & Grype scan reports
├── test/
│   ├── compat_test.py                 # Automated side-by-side HTTP & container compatibility test suite
│   └── run_scans.py                   # Automated Trivy/Grype/OpenVEX scanner runner
├── PLAN.md                            # Assignment task breakdown and execution checklist
└── .github/workflows/
    └── build-patch-ship.yml           # GitHub Actions CI/CD: builds .deb + image, scans, tests, pushes
```

---

## Quick Start & Build Instructions

### Option 1: One-Command Build & Test (`Makefile`)

```bash
# 1. Build nginx_1.25.5-1~bookworm_amd64.deb from upstream source with CVE-2024-7347.patch
#    inside a clean debian:bookworm-slim container -> outputs to build/out/
make deb

# 2. Build the final drop-in replacement image (nginx:1.25-bookworm-patched)
make image

# 3. Run the automated compatibility test suite against upstream nginx:1.25-bookworm
make test

# 4. Run Trivy & Grype baseline, patched, and VEX-filtered vulnerability scans
make scan

# Or run the full build + test loop in one command:
make all
```

### Option 2: Direct Docker & Python Commands (Cross-Platform / Windows / Linux)

```bash
# 1. Build .deb package in clean-room debian:bookworm-slim builder and export to build/out/
docker build -f build/Dockerfile --target builder -t echo-nginx-deb-builder .
docker run --rm -v "$(pwd)/build/out:/host_out" echo-nginx-deb-builder cp -a /out/. /host_out/

# 2. Build final container image from Containerfile
docker build -f Containerfile -t nginx:1.25-bookworm-patched .

# 3. Run automated compatibility test suite
python3 test/compat_test.py

# 4. Run Trivy & Grype scans (baseline, patched, and VEX-filtered)
python3 test/run_scans.py
```

### Option 3: GitHub Actions Automated Pipeline

Every push to `main` (or manual trigger via `workflow_dispatch`) executes [`.github/workflows/build-patch-ship.yml`](.github/workflows/build-patch-ship.yml), which builds the `.deb` package and container image from source, runs `make test`, runs Trivy/Grype/OpenVEX scans, and publishes the image to GitHub Container Registry (`ghcr.io`).

---

## Image Size Comparison

| Image | Base | Uncompressed Size (Bytes) | Size (MiB) | Difference |
| :--- | :--- | :---: | :---: | :---: |
| **Upstream (`nginx:1.25-bookworm`)** | `debian:bookworm-slim` (May 2024 snapshot) | `187,659,947` | `178.97 MiB` | Baseline |
| **Patched (`nginx:1.25-bookworm-patched`)** | `debian:bookworm-slim` (Debian 12.15) | `176,150,057` | `167.99 MiB` | **-11.51 MB (-6.13%)** |

---

## Vulnerability Scan Summary (Baseline vs. Patched vs. Patched + VEX)

| Scanner | Baseline (`nginx:1.25-bookworm`) | Patched (`nginx:1.25-bookworm-patched`) | Patched + OpenVEX (`vex.openvex.json`) | Total CVEs Eliminated |
| :--- | :---: | :---: | :---: | :---: |
| **Trivy (`v0.76.2`)** | **839** (`CRIT: 21, HIGH: 181, MED: 322, LOW: 265, UNK: 50`) | **359** (`CRIT: 3, HIGH: 70, MED: 125, LOW: 122, UNK: 39`) | **359** (`CRIT: 3, HIGH: 70, MED: 125, LOW: 122, UNK: 39`) | **-480 CVEs (-57.2%)** (`18/21` Criticals eliminated) |
| **Grype (`v0.121.2`)** | **952** | **357** | **356** | **-596 CVEs (-62.6%)** |

Full scan outputs are saved in:
- [`baseline-trivy.txt`](baseline-trivy.txt) & [`baseline-grype.txt`](baseline-grype.txt)
- [`scans/patched-trivy.txt`](scans/patched-trivy.txt) & [`scans/patched-grype.txt`](scans/patched-grype.txt)
- [`scans/patched-trivy-vex.txt`](scans/patched-trivy-vex.txt) & [`scans/patched-grype-vex.txt`](scans/patched-grype-vex.txt)

---

## Target CVE Remediation Table

Following the assignment guidance (*"Focus on doing a couple of CVEs end-to-end, not many CVEs partially. Two well-fixed beats ten half-fixed"*), we targeted two core CVEs using the two required remediation techniques:

| CVE ID | Severity | Package / Component | Fix Method | Upstream Evidence / Commit Link | Verification (Baseline -> Patched / VEX) |
| :--- | :---: | :--- | :--- | :--- | :--- |
| **CVE-2024-7347** | **MEDIUM** (5.7) | `nginx` (`1.25.5` — `src/http/modules/ngx_http_mp4_module.c`) | **Backport Patch** ([`build/patches/CVE-2024-7347.patch`](build/patches/CVE-2024-7347.patch)) | [Commit `a0d386416c9d`](https://github.com/nginx/nginx/commit/a0d386416c9d03c2a1f4a3f15b79f8b3c22e30c1) / [Official NGINX Patch `patch.2024.mp4.txt`](https://nginx.org/download/patch.2024.mp4.txt) | Fixes 32-bit integer overflow (`n = (uint64_t) (next_chunk - chunk) * samples`) and unordered `stsc` chunk buffer over-read in `ngx_http_mp4_crop_stsc_data()`. Verified in source build (`grep -q "unordered mp4 stsc chunks"`) and suppressed via OpenVEX in [`scans/patched-grype-vex.txt`](scans/patched-grype-vex.txt) (`1 -> 0`). |
| **CVE-2024-4741** | **HIGH / MEDIUM** (7.5 / 5.9) | `libssl3` / `openssl` | **Dependency Version Bump** (`3.0.11-1~deb12u2` -> `3.0.22-1~deb12u2`) | [OpenSSL Advisory](https://www.openssl.org/news/secadv/20240527.txt) / [Debian Security Tracker `CVE-2024-4741`](https://security-tracker.debian.org/tracker/CVE-2024-4741) | Fixes OpenSSL `SSL_free_buffers` Use-After-Free memory corruption (fixed in `>= 3.0.14-1~deb12u1`). Enforced in `.deb` `DEBIAN/control` (`Depends: libssl3 (>= 3.0.14)`) and upgraded in [`Containerfile`](Containerfile). Eliminated in both [`scans/patched-trivy.txt`](scans/patched-trivy.txt) (`2 -> 0`) and [`scans/patched-grype.txt`](scans/patched-grype.txt) (`2 -> 0`). |

*(In addition to `CVE-2024-4741`, bumping the `debian:bookworm-slim` runtime libraries and omitting unused build-time packages like `curl`/`libcurl4` eliminated **480 CVEs in Trivy** and **596 CVEs in Grype** across `libssl3`, `libpcre2-8-0`, `libexpat1`, `libxml2`, `libxslt1.1`, `libpng16-16`, and `libc6`.)*

---

## VEX Attestation (`vex.openvex.json`) & Scanner Verification

Because vulnerability scanners match binaries and packages by version string (`nginx` `1.25.5` / `1.25.5-1~bookworm`), backporting a source patch onto `nginx 1.25.5` does not change the version string.

We provide [`vex.openvex.json`](vex.openvex.json) (an **OpenVEX v0.2.0** document) declaring `CVE-2024-7347` as `"not_affected"` with justification `"inline_mitigations_already_exist"`:

```bash
# Scan with Grype without VEX (flags CVE-2024-7347 on the /usr/sbin/nginx 1.25.5 binary: 357 findings)
grype nginx:1.25-bookworm-patched

# Scan with Grype with OpenVEX applied (CVE-2024-7347 disappears: 357 -> 356 findings)
grype nginx:1.25-bookworm-patched --vex vex.openvex.json

# Scan with Trivy with OpenVEX applied
trivy image --vex vex.openvex.json nginx:1.25-bookworm-patched
```

---

## Automated Compatibility Test Suite (`test/compat_test.py`)

### What "Working Correctly" Means for a Drop-In Replacement
A true drop-in replacement for `nginx:1.25-bookworm` must satisfy two contracts:
1. **Container Runtime & Orchestration Contract**:
   - Identical `Entrypoint` (`["/docker-entrypoint.sh"]`), `Cmd` (`["nginx", "-g", "daemon off;"]`), `ExposedPorts` (`80/tcp`), `StopSignal` (`SIGQUIT`), and `WorkingDir`.
   - Identical unprivileged worker user/group (`uid=101(nginx) gid=101(nginx)`).
   - Identical `/docker-entrypoint.d/*` initialization hook behavior (IPv6 auto-detection + `dpkg-query` conffile MD5 check, `15-local-resolvers.envsh`, `20-envsubst-on-templates.sh` environment variable substitution on `/etc/nginx/templates/*.template`).
2. **HTTP Protocol & Module Behavior Contract**:
   - For identical HTTP and raw TCP inputs, the replacement container must return the **exact same HTTP status code, response headers (normalizing only volatile wall-clock `Date` / `Last-Modified` / `ETag` timestamps while still asserting header presence), and byte-for-byte response body**.

### Verified Test Results (`scans/compat-test-results.txt`)

All **19 checks across 3 phases** pass with `0` mismatches:

| Phase | Scenario | Result |
| :--- | :--- | :--- |
| **Phase 1: Metadata & Runtime** | `Entrypoint`, `Cmd`, `ExposedPorts`, `WorkingDir`, `StopSignal`, `nginx -v`, `id nginx` | `PASS` (7/7 matched) |
| **Phase 2: Default Config** | `GET /` (`200 OK`), `HEAD /` (`200 OK`), `GET /50x.html` (`200 OK`), `GET /does-not-exist` (`404`), `POST /` (`405`), Malformed Header over Raw TCP (`400`), Malformed Request Line over Raw TCP (`400`) | `PASS` (7/7 matched) |
| **Phase 3: Custom Config** | `GET /custom-health` via `20-envsubst-on-templates.sh` (`200`), `POST /upload` 1KB (`200`), `POST /upload` 16KB exceeding `client_max_body_size` (`413`), `GET /rewrite-test/books/99` (`200` regex capture), `GET /gzip-payload` (`200` gzip decompression) | `PASS` (5/5 matched) |

---

## Residual Risk Assessment

### What Remains in the Patched Image & Why
1. **Unfixed Upstream Debian Bookworm Base OS CVEs (`libc6`, `perl-base`, `gcc-12-base`, `libsystemd0`, `libtiff6`, `libxml2` `will_not_fix` / `no-dsa` advisories)**:
   - Of the 359 remaining findings in Trivy (356 in Grype), the vast majority are Debian `will_not_fix` / `no-dsa` entries in `debian:bookworm-slim` base packages (`perl-base`, `libc6`, `libsystemd0`, `libxml2`, `libheif1`, `libgd3`) where Debian has not issued a Bookworm package update.
2. **Remaining EOL NGINX `1.25.5` Upstream Advisories**:
   - Because `1.25.x` reached EOL in May 2024, scanners matching the `1.25.5` version string flag later advisories fixed in `1.26.1+` / `1.27.x+` (such as experimental HTTP/3 QUIC advisories `CVE-2024-31079`, `CVE-2024-32760`, `CVE-2024-34161`, `CVE-2024-35200`).

### What We Would Do Next in Production
1. **Backport Remaining HTTP/3 & Core NGINX Patches**: Add upstream patches for `CVE-2024-31079`, `CVE-2024-32760`, `CVE-2024-34161`, and `CVE-2024-35200` into `build/patches/` and `vex.openvex.json`.
2. **Compile Unfixed Upstream Libraries from Source or Strip Optional Dynamic Modules**: If workloads do not require `ngx_http_image_filter_module.so` or `ngx_http_xslt_filter_module.so`, omitting `libgd3` (`libheif1`, `libaom3`, `libtiff6`, `libde265-0`) and `libxslt1.1` (`libxml2`) eliminates over 100 transitive media-library CVEs.
3. **Attach OpenVEX as a Signed OCI Attestation (`cosign attest --type openvex`)**: Publish the OpenVEX document directly alongside the image digest in GHCR so `trivy image --vex oci` and `grype` consume it automatically.

---

## Engineering Notes & Retrospective

### What Surprised Us
1. **Why Grype Flags `CVE-2024-7347` on `nginx 1.25.5` While Trivy Does Not**:
   - **Grype** includes a binary analyzer that extracts the version `1.25.5` from `/usr/sbin/nginx` and matches it against NVD CPE ranges (`< 1.26.2` / `< 1.27.1`), flagging `CVE-2024-7347` on the `binary` package type (and suppressing it when `--vex vex.openvex.json` is passed).
   - **Trivy**, by contrast, evaluates Debian packages in `/var/lib/dpkg/status` against the Debian Bookworm Security Tracker. Because Debian Bookworm's own `nginx` package is `1.22.1-9+deb12u2` (where Debian backported `CVE-2024-7347`), and `1.25.5-1~bookworm` sorts as `> 1.22.1-9+deb12u2` in `dpkg`, Trivy considers `1.25.5-1~bookworm` already newer than Debian's fixed version (`1.22.1-9+deb12u2`)!
2. **Sourcing `15-local-resolvers.envsh` inside `/docker-entrypoint.sh`**:
   - `/docker-entrypoint.sh` executes `*.sh` scripts as subprocesses, but **sources** `*.envsh` files (`. "$f"`) inside a `while read -r f` pipeline subshell. Using `exit 0` instead of `return 0` inside `15-local-resolvers.envsh` prematurely terminates the `while` loop before `20-envsubst-on-templates.sh` runs. Syncing the exact `return 0` behavior from upstream resolved our Phase 3 template `envsubst` test immediately.
3. **`10-listen-on-ipv6-by-default.sh` checks `dpkg-query` conffile MD5 checksums**:
   - The official `/docker-entrypoint.d/10-listen-on-ipv6-by-default.sh` script queries `dpkg-query --show --showformat='${Conffiles}\n' nginx` and verifies the MD5 checksum of `/etc/nginx/conf.d/default.conf` before enabling IPv6. Declaring `/etc/nginx/conf.d/default.conf` in `DEBIAN/conffiles` when building `nginx_1.25.5-1~bookworm_amd64.deb` ensured `dpkg` registered the exact checksum automatically.

### How AI Tools Were Used
- Used **Antigravity (Google DeepMind agentic coding assistant)** to:
  - Extract upstream `nginx:1.25-bookworm` `./configure` flags, entrypoint scripts, and package layout.
  - Backport upstream NGINX commit `a0d386416c9d03c2a1f4a3f15b79f8b3c22e30c1` (`CVE-2024-7347.patch`) onto `nginx 1.25.5` and verify its application during the `.deb` build.
  - Author the OpenVEX v0.2.0 attestation (`vex.openvex.json`) and automated compatibility test suite (`test/compat_test.py`).
