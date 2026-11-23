/* RODIKIL // motor das intros: sincroniza animações CSS (classe .play no <body>) com o som (Web Audio).
   - No OBS (Browser Source, "Reiniciar quando a cena ficar ativa") toca sozinha toda vez que a cena entra.
   - No navegador, o Chrome/Edge bloqueia som sem clique: aparece o botão "ASSISTIR COM SOM" e, no fim, "REPETIR".
   - ?auto=1 força iniciar sem clique (usado para gerar prévias). */
(function () {
  "use strict";

  function fit() {
    const stage = document.getElementById("stage");
    const s = Math.min(window.innerWidth / 1920, window.innerHeight / 1080);
    stage.style.transform = s === 1 ? "" : "translate(-50%, -50%) scale(" + s + ")";
    stage.classList.toggle("is-scaled", s !== 1);
  }

  function run(opts) {
    const sfx = window.RKSfx.create();
    const inObs = !!window.obsstudio;
    const auto = new URLSearchParams(location.search).get("auto") === "1";
    let timers = [];

    const gate = document.createElement("button");
    gate.className = "rk-gate";
    gate.innerHTML = '<span class="rk-pill is-red"><i class="rk-dot"></i><span class="rk-label">▶ ASSISTIR COM SOM</span></span>';
    const replay = document.createElement("button");
    replay.className = "rk-replay";
    replay.innerHTML = '<span class="rk-pill is-outline"><i class="rk-dot"></i><span class="rk-label">↻ REPETIR</span></span>';

    function start() {
      gate.remove(); replay.remove();
      timers.forEach(clearTimeout); timers = [];
      document.body.classList.remove("play", "done");
      void document.body.offsetWidth; // reinicia as animações CSS
      const t0 = sfx.ctx.currentTime + 0.05;
      document.body.classList.add("play");
      if (opts.sound) opts.sound(sfx, t0);
      (opts.steps || []).forEach(function (s) { timers.push(setTimeout(s[1], s[0] * 1000 + 50)); });
      timers.push(setTimeout(function () {
        document.body.classList.add("done");
        if (!inObs) document.body.appendChild(replay);
      }, opts.duration * 1000 + 100));
    }

    gate.onclick = function () { sfx.ctx.resume().then(start); };
    replay.onclick = function () { sfx.ctx.resume().then(start); };

    const fontsReady = Promise.race([
      document.fonts ? document.fonts.ready : Promise.resolve(),
      new Promise(function (r) { setTimeout(r, 1500); })
    ]);
    fontsReady.then(function () {
      if (auto || inObs || sfx.ctx.state === "running") start();
      else document.body.appendChild(gate);
    });
  }

  window.addEventListener("resize", fit);
  document.addEventListener("DOMContentLoaded", fit);
  window.RKIntro = { run: run };
})();
