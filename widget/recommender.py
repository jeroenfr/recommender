"""Item-based "customers also bought" recommender.

Learns from order history: two products are similar when they often appear
in the same order. Similarity is the cosine of co-occurrence,
    sim(a, b) = n(a, b) / sqrt(n(a) * n(b))
which keeps popular products from dominating every list. Products without
enough co-purchases fall back to the overall best sellers.
"""

import csv
import math
from collections import Counter, defaultdict
from itertools import combinations


class Recommender:
    def __init__(self, orders, products=None, min_co_count=2, max_neighbours=50):
        """orders: iterable of (order_id, product_id) rows.
        products: dict product_id -> metadata dict (name, price, url, image).
        min_co_count: minimum number of shared orders before a pair counts.
        """
        self.products = products or {}
        self.min_co_count = min_co_count

        baskets = defaultdict(set)
        for order_id, product_id in orders:
            baskets[order_id].add(product_id)

        self.item_counts = Counter()
        co_counts = Counter()
        for items in baskets.values():
            self.item_counts.update(items)
            for a, b in combinations(sorted(items), 2):
                co_counts[(a, b)] += 1

        neighbours = defaultdict(list)
        for (a, b), n in co_counts.items():
            if n < min_co_count:
                continue
            sim = n / math.sqrt(self.item_counts[a] * self.item_counts[b])
            neighbours[a].append((b, sim))
            neighbours[b].append((a, sim))

        self.neighbours = {
            item: sorted(sims, key=lambda s: (-s[1], s[0]))[:max_neighbours]
            for item, sims in neighbours.items()
        }
        self.popular = [item for item, _ in sorted(
            self.item_counts.items(), key=lambda c: (-c[1], c[0]))]
        self.n_orders = len(baskets)

    @classmethod
    def from_csv(cls, orders_path, products_path=None, **kwargs):
        with open(orders_path, newline="", encoding="utf-8") as f:
            orders = [(r["order_id"], r["product_id"]) for r in csv.DictReader(f)]
        products = {}
        if products_path:
            with open(products_path, newline="", encoding="utf-8") as f:
                products = {r["product_id"]: r for r in csv.DictReader(f)}
        return cls(orders, products, **kwargs)

    def recommend(self, product_ids, k=4, exclude=()):
        """Recommend k products for a product page or a cart.

        Scores are summed over all given products, so a cart with several
        items gets recommendations that fit the basket as a whole.
        Returns a list of dicts with product_id, score, reason and metadata.
        """
        seen = set(product_ids) | set(exclude)
        scores = defaultdict(float)
        for pid in product_ids:
            for other, sim in self.neighbours.get(pid, ()):
                if other not in seen:
                    scores[other] += sim

        ranked = sorted(scores.items(), key=lambda s: (-s[1], s[0]))[:k]
        results = [self._result(pid, round(score, 4), "also_bought")
                   for pid, score in ranked]

        # Top up with best sellers when there is too little co-purchase data.
        chosen = seen | {r["product_id"] for r in results}
        for pid in self.popular:
            if len(results) >= k:
                break
            if pid not in chosen:
                results.append(self._result(pid, 0.0, "popular"))
                chosen.add(pid)
        return results

    def _result(self, product_id, score, reason):
        meta = self.products.get(product_id, {})
        return {
            "product_id": product_id,
            "score": score,
            "reason": reason,
            "name": meta.get("name", product_id),
            "price": meta.get("price"),
            "url": meta.get("url"),
            "image": meta.get("image"),
        }
