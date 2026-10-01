import json
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from recommender import Recommender  # noqa: E402
from server import Stats, make_handler  # noqa: E402

ORDERS = [
    ("o1", "machine"), ("o1", "beans"), ("o1", "jug"),
    ("o2", "machine"), ("o2", "beans"),
    ("o3", "machine"), ("o3", "jug"),
    ("o4", "teapot"), ("o4", "tea"),
    ("o5", "teapot"), ("o5", "tea"),
    ("o6", "beans"),
    ("o7", "beans"),
]


class RecommenderTest(unittest.TestCase):
    def setUp(self):
        self.rec = Recommender(ORDERS, {"beans": {"name": "Bonen", "price": "9.95"}})

    def test_co_purchased_items_rank_first(self):
        ids = [r["product_id"] for r in self.rec.recommend(["machine"], k=2)]
        self.assertEqual(set(ids), {"beans", "jug"})

    def test_cosine_downweights_popular_items(self):
        # jug: 2 shared orders out of 2; beans: 2 out of 4 -> jug ranks higher.
        recs = self.rec.recommend(["machine"], k=2)
        self.assertEqual(recs[0]["product_id"], "jug")
        self.assertGreater(recs[0]["score"], recs[1]["score"])

    def test_never_recommends_input_or_excluded(self):
        ids = [r["product_id"] for r in self.rec.recommend(["machine", "jug"], k=5, exclude=["tea"])]
        self.assertNotIn("machine", ids)
        self.assertNotIn("jug", ids)
        self.assertNotIn("tea", ids)

    def test_unknown_product_falls_back_to_popular(self):
        recs = self.rec.recommend(["does-not-exist"], k=2)
        self.assertEqual([r["reason"] for r in recs], ["popular", "popular"])
        self.assertEqual(recs[0]["product_id"], "beans")

    def test_min_co_count_filters_rare_pairs(self):
        rec = Recommender([("o1", "a"), ("o1", "b")], min_co_count=2)
        self.assertEqual(rec.recommend(["a"], k=1)[0]["reason"], "popular")

    def test_results_carry_product_metadata(self):
        beans = next(r for r in self.rec.recommend(["machine"], k=2) if r["product_id"] == "beans")
        self.assertEqual(beans["name"], "Bonen")
        self.assertEqual(beans["price"], "9.95")

    def test_cart_scores_are_summed(self):
        recs = self.rec.recommend(["machine", "jug"], k=1)
        self.assertEqual(recs[0]["product_id"], "beans")


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rec = Recommender(ORDERS)
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(rec, Stats()))
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def get(self, path):
        with urlopen(self.base + path) as r:
            return r.status, r.headers, r.read()

    def post(self, path, data):
        req = Request(self.base + path, data=data, headers={"Content-Type": "text/plain"})
        with urlopen(req) as r:
            return json.loads(r.read())

    def test_recommendations_endpoint(self):
        status, headers, body = self.get("/api/recommendations?product=machine&k=2")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Access-Control-Allow-Origin"], "*")
        self.assertEqual(len(json.loads(body)["recommendations"]), 2)

    def test_missing_product_is_400(self):
        with self.assertRaises(HTTPError) as ctx:
            self.get("/api/recommendations")
        self.assertEqual(ctx.exception.code, 400)

    def test_bad_k_is_400(self):
        with self.assertRaises(HTTPError) as ctx:
            self.get("/api/recommendations?product=machine&k=abc")
        self.assertEqual(ctx.exception.code, 400)

    def test_tracking_updates_stats(self):
        before = json.loads(self.get("/api/stats")[2])
        self.post("/api/track", b'{"event": "impression", "product_id": "machine"}')
        self.post("/api/track", b'{"event": "click", "product_id": "beans"}')
        after = json.loads(self.get("/api/stats")[2])
        self.assertEqual(after["impressions"], before["impressions"] + 1)
        self.assertEqual(after["clicks"], before["clicks"] + 1)

    def test_invalid_event_is_400(self):
        with self.assertRaises(HTTPError) as ctx:
            self.post("/api/track", b'{"event": "hack"}')
        self.assertEqual(ctx.exception.code, 400)

    def test_serves_widget_script(self):
        status, headers, body = self.get("/widget.js")
        self.assertEqual(status, 200)
        self.assertIn("javascript", headers["Content-Type"])
        self.assertIn(b"data-recs-product", body)


if __name__ == "__main__":
    unittest.main()
