/*
 * "Customers also bought" widget.
 *
 * Usage on any shop page:
 *   <div data-recs-product="P01" data-recs-title="Vaak samen gekocht" data-recs-k="4"></div>
 *   <script src="https://YOUR-HOST/widget.js" defer></script>
 *
 * Several products (e.g. a cart) can be given comma-separated: data-recs-product="P01,P02".
 * Rendering happens inside a Shadow DOM so shop CSS and widget CSS do not clash.
 */
(function () {
  "use strict";

  var script = document.currentScript;
  var API = script ? new URL(script.src).origin : "";

  var STYLE = [
    ":host{display:block;font-family:system-ui,-apple-system,Segoe UI,sans-serif;color:#1f2328}",
    "h3{font-size:1.05rem;margin:0 0 .75rem}",
    ".grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px}",
    "a.card{display:flex;flex-direction:column;gap:6px;padding:10px;border:1px solid #d0d7de;",
    "border-radius:10px;text-decoration:none;color:inherit;background:#fff;transition:box-shadow .15s}",
    "a.card:hover{box-shadow:0 2px 10px rgba(0,0,0,.12)}",
    ".img{aspect-ratio:1;border-radius:8px;background:#f3ede6;display:flex;align-items:center;",
    "justify-content:center;font-size:2rem;font-weight:600;color:#8a5a3b;overflow:hidden}",
    ".img img{width:100%;height:100%;object-fit:cover}",
    ".name{font-size:.9rem;line-height:1.3}",
    ".price{font-weight:600}",
  ].join("");

  function safeUrl(url) {
    if (!url) return "#";
    try {
      var u = new URL(url, window.location.href);
      return u.protocol === "http:" || u.protocol === "https:" ? u.href : "#";
    } catch (e) {
      return "#";
    }
  }

  function track(event, productId) {
    // text/plain avoids a CORS preflight; keepalive survives page navigation.
    try {
      fetch(API + "/api/track", {
        method: "POST",
        headers: { "Content-Type": "text/plain" },
        body: JSON.stringify({ event: event, product_id: productId }),
        keepalive: true,
      });
    } catch (e) { /* tracking must never break the shop */ }
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function card(rec) {
    var a = el("a", "card");
    a.href = safeUrl(rec.url);
    var img = el("div", "img");
    if (rec.image) {
      var i = document.createElement("img");
      i.src = safeUrl(rec.image);
      i.alt = rec.name;
      i.loading = "lazy";
      img.appendChild(i);
    } else {
      img.textContent = (rec.name || "?").charAt(0);
    }
    a.appendChild(img);
    a.appendChild(el("span", "name", rec.name));
    if (rec.price) {
      var price = Number(rec.price);
      a.appendChild(el("span", "price", isNaN(price) ? rec.price : "€ " + price.toFixed(2).replace(".", ",")));
    }
    a.addEventListener("click", function () { track("click", rec.product_id); });
    return a;
  }

  function render(container) {
    var products = (container.getAttribute("data-recs-product") || "")
      .split(",").map(function (s) { return s.trim(); }).filter(Boolean);
    if (!products.length) return;
    var k = parseInt(container.getAttribute("data-recs-k") || "4", 10) || 4;
    var title = container.getAttribute("data-recs-title") || "Klanten kochten ook";

    var params = new URLSearchParams({ k: String(k) });
    products.forEach(function (p) { params.append("product", p); });

    fetch(API + "/api/recommendations?" + params)
      .then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); })
      .then(function (data) {
        var recs = data.recommendations || [];
        if (!recs.length) return;
        var root = container.shadowRoot || container.attachShadow({ mode: "open" });
        root.innerHTML = "";
        var style = document.createElement("style");
        style.textContent = STYLE;
        root.appendChild(style);
        root.appendChild(el("h3", null, title));
        var grid = el("div", "grid");
        recs.forEach(function (rec) { grid.appendChild(card(rec)); });
        root.appendChild(grid);
        track("impression", products.join(","));
      })
      .catch(function () { /* fail silently: no widget is better than a broken page */ });
  }

  function init() {
    var nodes = document.querySelectorAll("[data-recs-product]");
    Array.prototype.forEach.call(nodes, render);
  }

  window.RecsWidget = { refresh: init };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
