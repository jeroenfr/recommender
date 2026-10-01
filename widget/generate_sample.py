"""Generate a synthetic order history for a small coffee webshop.

Customers tend to buy products from the same "theme" together (e.g. an
espresso machine with beans and a milk jug), plus some random noise, so the
recommender has realistic structure to learn from.
"""

import csv
import random
from pathlib import Path

PRODUCTS = [
    # product_id, name, price, theme
    ("P01", "Espressomachine Barista", "349.00", "espresso"),
    ("P02", "Espressobonen Napoli 1kg", "18.50", "espresso"),
    ("P03", "Melkopschuimkan RVS", "14.95", "espresso"),
    ("P04", "Tamper 58mm", "24.00", "espresso"),
    ("P05", "Ontkalker espresso", "9.95", "espresso"),
    ("P06", "Cappuccinokopjes (set van 4)", "22.00", "espresso"),
    ("P07", "V60 dripper", "21.00", "filter"),
    ("P08", "Filterpapier V60 (100 st.)", "6.50", "filter"),
    ("P09", "Waterkoker met tuit", "54.00", "filter"),
    ("P10", "Filterbonen Ethiopie 250g", "11.95", "filter"),
    ("P11", "Weegschaal met timer", "29.00", "filter"),
    ("P12", "Handmolen keramisch", "39.00", "filter"),
    ("P13", "French press 1L", "27.50", "french"),
    ("P14", "Grove maling Colombia 500g", "12.50", "french"),
    ("P15", "Thermosbeker", "19.95", "french"),
    ("P16", "Groene thee sencha", "8.95", "tea"),
    ("P17", "Theepot gietijzer", "44.00", "tea"),
    ("P18", "Theefilters (100 st.)", "4.50", "tea"),
    ("P19", "Earl Grey losse thee", "7.95", "tea"),
    ("P20", "Cadeaubon 25 euro", "25.00", "gift"),
]


def generate(n_orders=2000, seed=42):
    rng = random.Random(seed)
    by_theme = {}
    for pid, _, _, theme in PRODUCTS:
        by_theme.setdefault(theme, []).append(pid)
    themes = list(by_theme)
    all_ids = [p[0] for p in PRODUCTS]

    rows = []
    for i in range(1, n_orders + 1):
        order_id = f"O{i:05d}"
        theme = rng.choice(themes)
        size = rng.choice([1, 2, 2, 3, 3, 4])
        basket = set(rng.sample(by_theme[theme], min(size, len(by_theme[theme]))))
        if rng.random() < 0.25:  # noise: an unrelated impulse buy
            basket.add(rng.choice(all_ids))
        rows.extend((order_id, pid) for pid in sorted(basket))
    return rows


def main():
    out = Path(__file__).parent / "sample"
    out.mkdir(exist_ok=True)
    with open(out / "products.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["product_id", "name", "price", "url", "image"])
        for pid, name, price, _ in PRODUCTS:
            w.writerow([pid, name, price, f"/demo/?product={pid}", ""])
    with open(out / "orders.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["order_id", "product_id"])
        w.writerows(generate())
    print(f"Wrote sample data to {out}")


if __name__ == "__main__":
    main()
