(function () {
  "use strict";
  const PRESETS = ["iniciando", "intervalo", "encerrando", "resenha"];
  let tela = Rodikil.param("tela", "iniciando");
  if (!PRESETS.includes(tela)) tela = "iniciando";

  document.body.dataset.tela = tela;
  const tpl = document.getElementById("tpl-" + tela);
  document.getElementById("content").appendChild(tpl.content.cloneNode(true));

  // Contagem regressiva opcional (?countdown=segundos) — só na tela "iniciando".
  const secs = parseInt(Rodikil.param("countdown", "0"), 10);
  const el = document.getElementById("countdown");
  if (el && secs > 0) {
    const end = Date.now() + secs * 1000;
    el.hidden = false;
    const tick = function () {
      const left = Math.max(0, Math.round((end - Date.now()) / 1000));
      const m = String(Math.floor(left / 60)).padStart(2, "0");
      const s = String(left % 60).padStart(2, "0");
      el.textContent = left > 0 ? m + ":" + s : "É AGORA //";
      if (left > 0) setTimeout(tick, 250);
    };
    tick();
  }
})();
