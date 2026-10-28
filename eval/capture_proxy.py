"""Capture proxy: records a REAL interaction without touching robot code.

1. Run this on an intermediate host.
2. Point the robot's SEGB semantic logger base_url at this proxy (e.g. http://YOUR_PC:8080).
   Every POST /ttl is recorded (payload + wall-clock timestamp).
3. Ctrl-C to stop and save capture.

By default the request is also forwarded to the real backend. Use --no-forward
to capture WITHOUT publishing to the real SEGB (a synthetic 200 is returned so
the robot's logger keeps working).

The saved capture.json is the single source of truth for every experiment replay:
  - It's real TTL, i.e., capture for a real interaction with a real robot (in our case, TIAGo).
  - Its timestamps drive the realistic inter-log gaps.
  - Replays derive distinct sessions from it --> we generate experiment scripts from this TTL.
"""
import argparse
import json
import signal
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

from segb_bench.config import BASE_URL, PROXY_LISTEN

OUT = "capture.json"
FORWARD = True
captured: list[dict] = []


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # silence default logging
        pass

    def _proxy(self, method: str):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""

        if method == "POST" and self.path.rstrip("/") == "/ttl":
            try:
                payload = json.loads(body.decode("utf-8"))
                captured.append({
                    "ts": time.time(),
                    "ttl": payload.get("ttl_content", ""),
                    "user": payload.get("user", ""),
                })
                tag = "captured" if FORWARD else "captured (NOT forwarded)"
                print(f"[{tag}] #{len(captured)} ttl={len(payload.get('ttl_content',''))}B")
            except Exception as exc:  # pragma: no cover
                print("[capture] could not parse /ttl body:", exc)

        if not FORWARD:
            msg = b'{"status":"captured, not forwarded"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)
            return

        fwd_headers = {k: v for k, v in self.headers.items() if k.lower() != "host"}
        resp = requests.request(method, BASE_URL + self.path, data=body, headers=fwd_headers)
        self.send_response(resp.status_code)
        skip = {"transfer-encoding", "content-encoding", "connection", "content-length"}
        for k, v in resp.headers.items():
            if k.lower() not in skip:
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(resp.content)))
        self.end_headers()
        self.wfile.write(resp.content)

    def do_POST(self):
        self._proxy("POST")

    def do_GET(self):
        self._proxy("GET")


def _save(*_):
    with open(OUT, "w") as fh:
        json.dump({"payloads": captured}, fh, indent=2)
    print(f"\nSaved {len(captured)} payloads to {OUT} "
          f"(run inspect_capture.py to count triples per payload)")
    sys.exit(0)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-forward", action="store_true",
                    help="capture only; do NOT publish to the real SEGB")
    args = ap.parse_args()
    FORWARD = not args.no_forward

    signal.signal(signal.SIGINT, _save)
    mode = f"forwarding -> {BASE_URL}" if FORWARD else "CAPTURE ONLY (not touching SEGB)"
    print(f"Capture proxy on {PROXY_LISTEN}  |  mode: {mode}")
    print("Ctrl-C to save.")
    ThreadingHTTPServer(PROXY_LISTEN, Handler).serve_forever()