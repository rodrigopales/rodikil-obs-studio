(function () {
  "use strict";

  const TYPES = {
    inscrito:  { title: "NOVO INSCRITO", message: "BEM-VINDO À NAVE //" },
    superchat: { title: "SUPER CHAT",    message: "VALEU DEMAIS PELO APOIO //" },
    membro:    { title: "NOVO MEMBRO",   message: "AGORA É DA TRIPULAÇÃO //" },
    raid:      { title: "RAID CHEGANDO", message: "SEGURA QUE VEM GENTE //" }
  };
  const DURATION_MS = parseInt(Rodikil.param("duration", "6000"), 10);

  const box = document.getElementById("alert");
  const elTitle = document.getElementById("al-title");
  const elMsg = document.getElementById("al-msg");
  const queue = [];
  let busy = false;

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function render(a) {
    const preset = TYPES[a.type] || TYPES.inscrito;
    elTitle.textContent = (a.title || preset.title).toUpperCase();
    const who = a.user ? "<b>" + esc(String(a.user).toUpperCase()) + "</b> — " : "";
    elMsg.innerHTML = who + esc((a.message || preset.message).toUpperCase());
  }

  function next() {
    if (busy || queue.length === 0) return;
    busy = true;
    render(queue.shift());
    box.hidden = false;
    box.className = "alert is-in";
    setTimeout(function () {
      box.className = "alert is-out";
      setTimeout(function () { box.hidden = true; busy = false; next(); }, 500);
    }, DURATION_MS);
  }

  window.rodikilAlert = function (a) { queue.push(a || {}); next(); };

  // Evento disparado pelo vendor request "obs-browser/emit_event".
  window.addEventListener("rodikil-alert", function (e) { window.rodikilAlert(e.detail || {}); });

  if (Rodikil.param("demo", "0") === "1") {
    const demo = [
      { type: "inscrito", user: "Fulano" },
      { type: "superchat", user: "Ciclano", message: "R$ 20 — TAMO JUNTO" },
      { type: "membro", user: "Beltrano" },
      { type: "raid", user: "CanalAmigo" }
    ];
    let i = 0;
    window.rodikilAlert(demo[i++]);
    setInterval(function () { window.rodikilAlert(demo[i++ % demo.length]); }, DURATION_MS + 2000);
  }
})();
