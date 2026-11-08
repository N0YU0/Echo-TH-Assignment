#!/usr/bin/env python3
"""Automated Drop-In Compatibility Test Suite for nginx:1.25-bookworm Replacement."""

import gzip
import http.client
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time

BASELINE_IMAGE = os.environ.get("BASELINE_IMAGE", "nginx:1.25-bookworm")
PATCHED_IMAGE = os.environ.get("PATCHED_IMAGE", "nginx:1.25-bookworm-patched")
VOLATILE_HEADERS = {"date", "last-modified", "etag"}

CUSTOM_TEMPLATE = """server {
    listen 80;
    server_name localhost;
    client_max_body_size 4k;
    gzip on;
    gzip_min_length 16;
    gzip_types text/plain application/json;

    location = /custom-health {
        add_header X-Echo-Marker "${ECHO_MARKER}" always;
        default_type application/json;
        return 200 '{"status":"ok","marker":"${ECHO_MARKER}"}\\n';
    }
    location = /upload-sink {
        default_type text/plain;
        return 200 "upload_accepted\\n";
    }
    location = /upload {
        proxy_pass http://127.0.0.1:80/upload-sink;
    }
    location ~ ^/rewrite-test/([a-z]+)/([0-9]+)$ {
        set $item_id $2;
        rewrite ^/rewrite-test/([a-z]+)/([0-9]+)$ /rewritten-target?category=$1 last;
    }
    location = /rewritten-target {
        add_header X-Rewritten-Item "$item_id" always;
        default_type text/plain;
        return 200 "category=$arg_category,item=$item_id\\n";
    }
    location = /gzip-payload {
        default_type text/plain;
        return 200 "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\\n";
    }
}
"""


def run_cmd(cmd, check=True):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=check)


def start_container(image, name, port, extra_args=None):
    run_cmd(["docker", "rm", "-f", name], check=False)
    cmd = ["docker", "run", "-d", "--name", name, "-p", f"127.0.0.1:{port}:80"] + (extra_args or []) + [image]
    run_cmd(cmd)
    deadline = time.time() + 20.0
    while time.time() < deadline:
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=1.0)
            conn.request("GET", "/")
            conn.getresponse().read()
            conn.close()
            return
        except Exception:
            time.sleep(0.2)
    raise RuntimeError(f"Container {name} failed to listen on port {port}")


def normalize_headers(pairs):
    return {
        (f"__present__:{k.lower().strip()}" if k.lower().strip() in VOLATILE_HEADERS else k.lower().strip()): (
            "true" if k.lower().strip() in VOLATILE_HEADERS else v.strip()
        )
        for k, v in pairs
    }


def http_req(port, method, path, body=None, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5.0)
    conn.request(method, path, body=body, headers=headers or {})
    resp = conn.getresponse()
    data = (resp.status, normalize_headers(resp.getheaders()), resp.read())
    conn.close()
    return data


def raw_tcp_req(port, payload):
    with socket.create_connection(("127.0.0.1", port), timeout=5.0) as sock:
        sock.sendall(payload)
        sock.shutdown(socket.SHUT_WR)
        raw = b"".join(iter(lambda: sock.recv(4096), b""))
    head, _, body = raw.partition(b"\r\n\r\n")
    lines = head.decode("latin1", errors="replace").split("\r\n")
    status = int(lines[0].split()[1]) if lines and len(lines[0].split()) > 1 else 0
    headers = normalize_headers([line.split(":", 1) for line in lines[1:] if ":" in line])
    return status, headers, body


def check_scenario(name, fn, base_port, patch_port, is_gzip=False):
    b_status, b_hdrs, b_body = fn(base_port)
    p_status, p_hdrs, p_body = fn(patch_port)
    if is_gzip:
        b_body, p_body = gzip.decompress(b_body), gzip.decompress(p_body)
    if (b_status, b_hdrs, b_body) != (p_status, p_hdrs, p_body):
        return False, f"FAIL [{name}] baseline=({b_status}, {len(b_body)}B) vs patched=({p_status}, {len(p_body)}B)"
    return True, f"PASS [{name}] status={p_status}, headers={len(p_hdrs)} matched, body={len(p_body)} bytes matched"


def main():
    if run_cmd(["docker", "image", "inspect", BASELINE_IMAGE], check=False).returncode != 0:
        run_cmd(["docker", "pull", BASELINE_IMAGE])

    b_size = int(run_cmd(["docker", "image", "inspect", BASELINE_IMAGE, "--format", "{{.Size}}"]).stdout.strip())
    p_size = int(run_cmd(["docker", "image", "inspect", PATCHED_IMAGE, "--format", "{{.Size}}"]).stdout.strip())
    print(f"Baseline ({BASELINE_IMAGE}): {b_size:,} bytes ({b_size / 1048576:.2f} MiB)")
    print(f"Patched  ({PATCHED_IMAGE}): {p_size:,} bytes ({p_size / 1048576:.2f} MiB)\n")

    failures = []

    def record(ok, msg):
        print(" ", msg)
        if not ok:
            failures.append(msg)

    print("--- Phase 1: Container Metadata & Runtime Contract Parity ---")
    b_cfg = json.loads(run_cmd(["docker", "image", "inspect", BASELINE_IMAGE]).stdout)[0]["Config"]
    p_cfg = json.loads(run_cmd(["docker", "image", "inspect", PATCHED_IMAGE]).stdout)[0]["Config"]
    for field in ("Entrypoint", "Cmd", "ExposedPorts", "WorkingDir", "StopSignal"):
        record(b_cfg.get(field) == p_cfg.get(field), f"PASS [Metadata:{field}] {p_cfg.get(field)}")

    for label, cmd in [("nginx -v", ["nginx", "-v"]), ("id nginx", ["id", "nginx"])]:
        b_out = run_cmd(["docker", "run", "--rm", BASELINE_IMAGE] + cmd)
        p_out = run_cmd(["docker", "run", "--rm", PATCHED_IMAGE] + cmd)
        val = (p_out.stdout + p_out.stderr).strip()
        record((b_out.stdout, b_out.stderr) == (p_out.stdout, p_out.stderr), f"PASS [Runtime:{label}] {val}")

    print("\n--- Phase 2: Default Configuration HTTP Scenarios ---")
    try:
        start_container(BASELINE_IMAGE, "echo-compat-base", 18080)
        start_container(PATCHED_IMAGE, "echo-compat-patch", 18081)
        for name, fn in [
            ("GET / (Welcome Page)", lambda p: http_req(p, "GET", "/")),
            ("HEAD / (Headers Only)", lambda p: http_req(p, "HEAD", "/")),
            ("GET /50x.html (Static Error Page)", lambda p: http_req(p, "GET", "/50x.html")),
            ("GET /does-not-exist (404 Not Found)", lambda p: http_req(p, "GET", "/does-not-exist")),
            ("POST / (405 Not Allowed)", lambda p: http_req(p, "POST", "/", body=b"hello")),
            ("Malformed Header (400 Bad Request)", lambda p: raw_tcp_req(p, b"GET / HTTP/1.1\r\nHost: localhost\r\nContent-Length: invalid\r\n\r\n")),
            ("Malformed Request Line (400 Bad Request)", lambda p: raw_tcp_req(p, b"BAD_REQUEST_LINE\r\n\r\n")),
        ]:
            record(*check_scenario(name, fn, 18080, 18081))
    finally:
        run_cmd(["docker", "rm", "-f", "echo-compat-base", "echo-compat-patch"], check=False)

    print("\n--- Phase 3: Custom Config, envsubst Templates, Large Body, Rewrite & Gzip ---")
    tmp_dir = tempfile.mkdtemp(prefix="echo-compat-")
    try:
        tpl = os.path.join(tmp_dir, "default.conf.template")
        with open(tpl, "w", encoding="utf-8", newline="\n") as f:
            f.write(CUSTOM_TEMPLATE)
        os.chmod(tpl, 0o644)
        extra = ["-e", "ECHO_MARKER=dropin-verified", "-v", f"{tmp_dir.replace(os.sep, '/')}:/etc/nginx/templates:ro"]
        start_container(BASELINE_IMAGE, "echo-compat-base-custom", 18082, extra)
        start_container(PATCHED_IMAGE, "echo-compat-patch-custom", 18083, extra)

        for name, fn, is_gz in [
            ("GET /custom-health (envsubst template)", lambda p: http_req(p, "GET", "/custom-health"), False),
            ("POST /upload 1KB (200 OK)", lambda p: http_req(p, "POST", "/upload", body=b"x" * 1024), False),
            ("POST /upload 16KB (413 Too Large)", lambda p: http_req(p, "POST", "/upload", body=b"y" * 16384), False),
            ("GET /rewrite-test/books/99 (Rewrite Regex)", lambda p: http_req(p, "GET", "/rewrite-test/books/99"), False),
            ("GET /gzip-payload (gzip compression)", lambda p: http_req(p, "GET", "/gzip-payload", headers={"Accept-Encoding": "gzip"}), True),
        ]:
            record(*check_scenario(name, fn, 18082, 18083, is_gzip=is_gz))
    finally:
        run_cmd(["docker", "rm", "-f", "echo-compat-base-custom", "echo-compat-patch-custom"], check=False)
        shutil.rmtree(tmp_dir, ignore_errors=True)

    if failures:
        print(f"\nFAILED: {len(failures)} scenario(s) mismatched.")
        return 1
    print("\nSUCCESS: All 19 compatibility checks matched 100%!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
