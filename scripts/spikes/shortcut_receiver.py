"""Slice 0 spike: receive the iOS Shortcut's POST and save it as-is.

Run from the repo root:  python3 scripts/spikes/shortcut_receiver.py [port]

Standard library only. Each POST body is saved unchanged to spike_out/
(gitignored) and summarized in the terminal. This also proves the
iPhone -> Mac LAN path before Slice 3. Stop with Ctrl+C.
"""

import json
import socket
import sys
from collections import Counter
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

OUT_DIR = Path("spike_out")
MAX_BODY_BYTES = 1_000_000  # same limit the real ingest endpoint will use


def lan_ip() -> str:
    """Find the Mac's LAN IP. Connecting a UDP socket sends no packets."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]


def summarize(payload: object) -> None:
    """Print what we need to pin down the payload contract (ARCHITECTURE 6.2)."""
    if not isinstance(payload, dict):
        print(f"  top level is {type(payload).__name__}, not an object")
        return
    print(f"  top-level keys: {list(payload)}")
    print(f"  window: {payload.get('window')!r}   device_tz: {payload.get('device_tz')!r}")

    samples = payload.get("samples")
    if not isinstance(samples, list):
        print(f"  samples is {type(samples).__name__}, not a list")
        return

    counts = Counter(str(s.get("type")) for s in samples if isinstance(s, dict))
    print(f"  {len(samples)} samples by type: {dict(counts)}")
    for sample_type in counts:
        of_type = [s for s in samples if isinstance(s, dict) and str(s.get("type")) == sample_type]
        units = sorted({str(s.get("unit")) for s in of_type})
        print(f"  {sample_type}: units {units}")
        # Show raw values and timestamps exactly as sent, to see their formats.
        for s in of_type[:3]:
            value, start, source = s.get("value"), s.get("start"), s.get("source")
            print(f"    value={value!r} start={start!r} source={source!r}")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        # Open http://<mac-ip>:<port>/ in iPhone Safari to test the network path.
        self.reply(200, {"ok": True, "message": "receiver is up; POST the Shortcut here"})

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY_BYTES:
            self.reply(413, {"ok": False, "error": "body too large"})
            return
        body = self.rfile.read(length)

        # Microseconds so two quick runs never overwrite each other.
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        path = OUT_DIR / f"shortcut_{stamp}.json"
        OUT_DIR.mkdir(exist_ok=True)
        path.write_bytes(body)  # unchanged, so we see exactly what the Shortcut sent

        content_type = self.headers.get("Content-Type")
        print(f"\nPOST {self.path}  {length} bytes  Content-Type: {content_type}")
        print(f"  saved {path}")
        try:
            summarize(json.loads(body))
        except json.JSONDecodeError:
            print("  body is not JSON. First 500 characters:")
            print(body[:500].decode(errors="replace"))
        self.reply(200, {"ok": True, "saved": path.name, "bytes": length})

    def reply(self, status: int, data: dict) -> None:
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    # 0.0.0.0 so the iPhone on the same Wi-Fi can reach it.
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"Listening. Shortcut URL: http://{lan_ip()}:{port}/   (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
