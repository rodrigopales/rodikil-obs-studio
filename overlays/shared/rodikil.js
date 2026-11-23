/* RODIKIL // helpers compartilhados dos widgets (sem dependências). */
(function () {
  "use strict";

  /**
   * Lê um parâmetro do widget. Ordem: window.RK_PARAMS (definido no próprio HTML —
   * funciona com "Arquivo local" do OBS) → query string (teste no navegador / modo URL) → padrão.
   */
  function param(name, fallback) {
    const fixed = window.RK_PARAMS || {};
    if (fixed[name] !== undefined && fixed[name] !== "") return String(fixed[name]);
    const v = new URLSearchParams(window.location.search).get(name);
    return v === null || v === "" ? fallback : v;
  }

  /** PRNG determinístico — o céu fica idêntico a cada reload do OBS. */
  function mulberry32(seed) {
    return function () {
      seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
      let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  /** Desenha o campo de estrelas (textura Preto Glitter) num <canvas class="rk-stars">. */
  function drawStars(canvas, opts) {
    const o = Object.assign({ density: 0.0016, seed: 7 }, opts || {});
    const w = (canvas.width = canvas.clientWidth || window.innerWidth);
    const h = (canvas.height = canvas.clientHeight || window.innerHeight);
    const ctx = canvas.getContext("2d");
    const rnd = mulberry32(o.seed);
    ctx.clearRect(0, 0, w, h);
    const count = Math.round(w * h * o.density);
    for (let i = 0; i < count; i++) {
      const x = rnd() * w;
      const y = rnd() * h;
      const big = rnd() > 0.985;
      const r = big ? 1.1 + rnd() * 0.9 : 0.35 + rnd() * 0.6;
      const a = big ? 0.75 + rnd() * 0.25 : 0.15 + rnd() * 0.5;
      ctx.beginPath();
      ctx.fillStyle = "rgba(244,241,234," + a.toFixed(3) + ")";
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  window.Rodikil = { param: param, drawStars: drawStars };

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("canvas.rk-stars").forEach(function (c) {
      drawStars(c, { seed: Number(c.dataset.seed || 7) });
    });
  });
})();
