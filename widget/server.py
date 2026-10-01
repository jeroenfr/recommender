"""Tiny HTTP server for the recommendation widget (standard library only).

Endpoints:
  GET  /api/recommendations?product=P01[&product=P02][&k=4]
  POST /api/track      {"event": "impression"|"click", "product_id": ...}
  GET  /api/products   the product catalogue
  GET  /api/stats      impressions, clicks and click-through rate
  GET  /widget.js      the embeddable script
  GET  /demo/          a demo product page

Run:  python widget/server.py [--port 8000] [--orders ...] [--products ...]
"""

import argparse
import json
import mimetypes
import threading
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from recommender import Recommender

ROOT = Path(__file__).parent
STATIC_ROUTES = {
    "/widget.js": ROOT / "static" / "widget.js",
    "/demo/": ROOT / "demo" / "index.html",
}
MAX_K = 20


class Stats:
    def __init__(self):
        self._lock = threading.Lock()
        self.counts = Counter()

    def track(self, event):
        with self._lock:
            self.counts[event] += 1

    def summary(self):
        with self._lock:
            imp, clicks = self.counts["impression"], self.counts["click"]
        return {"impressions": imp, "clicks": clicks,
                "ctr": round(clicks / imp, 4) if imp else 0.0}


def make_handler(recommender, stats):
    class Handler(BaseHTTPRequestHandler):
        def do_OPTIONS(self):
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_GET(self):
            url = urlparse(self.path)
            if url.path == "/api/recommendations":
                q = parse_qs(url.query)
                products = q.get("product", [])
                if not products:
                    return self._json({"error": "missing 'product' parameter"}, 400)
                try:
                    k = max(1, min(MAX_K, int(q.get("k", ["4"])[0])))
                except ValueError:
                    return self._json({"error": "'k' must be an integer"}, 400)
                recs = recommender.recommend(products, k=k)
                return self._json({"products": products, "recommendations": recs})
            if url.path == "/api/products":
                return self._json({"products": list(recommender.products.values())})
            if url.path == "/api/stats":
                return self._json(stats.summary())
            if url.path in ("/", "/demo"):
                self.send_response(302)
                self.send_header("Location", "/demo/")
                return self.end_headers()
            path = STATIC_ROUTES.get(url.path)
            if path:
                return self._file(path)
            self._json({"error": "not found"}, 404)

        def do_POST(self):
            if urlparse(self.path).path != "/api/track":
                return self._json({"error": "not found"}, 404)
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(min(length, 10_000)) or b"{}")
            except (ValueError, json.JSONDecodeError):
                return self._json({"error": "invalid JSON"}, 400)
            event = body.get("event")
            if event not in ("impression", "click"):
                return self._json({"error": "event must be impression or click"}, 400)
            stats.track(event)
            self._json({"ok": True})

        def _cors(self):
            # The widget is embedded on the shop's own domain.
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

        def _json(self, data, status=200):
            body = json.dumps(data).encode()
            self.send_response(status)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _file(self, path):
            body = path.read_bytes()
            self.send_response(200)
            self._cors()
            ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--orders", default=ROOT / "sample" / "orders.csv")
    parser.add_argument("--products", default=ROOT / "sample" / "products.csv")
    parser.add_argument("--min-co-count", type=int, default=2)
    args = parser.parse_args()

    rec = Recommender.from_csv(args.orders, args.products,
                               min_co_count=args.min_co_count)
    print(f"Trained on {rec.n_orders} orders, {len(rec.item_counts)} products")
    server = ThreadingHTTPServer(("", args.port), make_handler(rec, Stats()))
    print(f"Demo: http://localhost:{args.port}/demo/")
    server.serve_forever()


if __name__ == "__main__":
    main()
