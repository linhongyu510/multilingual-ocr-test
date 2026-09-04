#!/usr/bin/env python3
"""Mock OCR service used to exercise the benchmark end-to-end without the real engine.

It mimics the behaviours observed in the recorded runs:
* returns the ground truth for well-supported languages (high accuracy),
* returns degraded text for partially-supported ones,
* rejects a configured set with HTTP 400 ("unsupported language").

Start it with:  python tools/mock_ocr_server.py --port 18110
"""

from __future__ import annotations

import argparse
import json
import random
import re
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """Serve each request on its own thread so concurrent clients are not queued."""

    daemon_threads = True

UNSUPPORTED = {"bn", "km", "kn", "lo", "ml", "my", "si"}
DEGRADED = {"hi": 0.25, "ne": 0.35, "ur": 0.45, "th": 0.60, "ug": 0.70, "ta": 0.75, "mn": 0.0}
DATASET_ROOT = Path("data/synthetic_30_samples_extended")


def degrade(text: str, keep: float, rng: random.Random) -> str:
    """Corrupt a fraction of characters to simulate imperfect recognition."""
    if keep >= 1.0:
        return text
    if keep <= 0.0:
        return ""
    chars = list(text)
    for i, ch in enumerate(chars):
        if ch.strip() and rng.random() > keep:
            chars[i] = rng.choice("x?#*")
    return "".join(chars)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args: object) -> None:  # silence per-request logging
        pass

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path in ("/health", "/healthz", "/"):
            self._send(200, {"status": "ok", "service": "mock-ocr"})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:
        if not self.path.startswith("/v1/ocr"):
            self._send(404, {"error": "not found"})
            return

        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)

        language = ""
        m = re.search(rb'name="language"\r\n\r\n(.*?)\r\n', raw, re.S)
        if m:
            language = m.group(1).decode("utf-8", "replace").strip()
        filename = ""
        m = re.search(rb'name="file"; filename="(.*?)"', raw)
        if m:
            filename = m.group(1).decode("utf-8", "replace")

        if language in UNSUPPORTED:
            self._send(400, {"error": f"unsupported language: {language}"})
            return

        stem = Path(filename).stem
        txt = DATASET_ROOT / language / f"{stem}.txt"
        ground_truth = txt.read_text(encoding="utf-8").strip() if txt.exists() else ""

        rng = random.Random(f"{language}/{stem}")
        keep = DEGRADED.get(language, 1.0)
        predicted = degrade(ground_truth, keep, rng)

        time.sleep(0.002)
        self._send(200, {"data": [{"text": predicted, "score": round(0.8 + 0.2 * keep, 3)}]})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=18110)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"mock OCR listening on http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
