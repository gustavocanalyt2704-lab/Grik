/* ATENDIDOS_1410 — "Pessoas atendidas hoje" no topo da aba Mensagens (atualiza a cada 15 s). */
(function () {
  const e = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const int = (n) => (Number(n) || 0).toLocaleString("pt-BR");
  async function tick() {
    const box = document.getElementById("atendidos-hoje");
    if (!box || box.hidden) return;
    try {
      const r = await fetch("/api/atendidos-hoje", { credentials: "same-origin", cache: "no-store" });
      const J = await r.json();
      if (!J.ok) return;
      const d = J.total - J.ontem.total;
      box.innerHTML = `<div class="at-card at-big"><div class="at-rot">Pessoas atendidas hoje</div><div class="at-num">${int(J.total)}</div>
        <div class="at-sub">Ontem (dia todo): <b>${int(J.ontem.total)}</b> · ${d >= 0 ? "+" : ""}${int(d)} · atualizado ${e(J.atualizado)}</div></div>
        <div class="at-grade">${J.instancias.map((i) => `<div class="at-card"><div class="at-rot">${e(i.inst)}</div><div class="at-n">${int(i.n)}</div><div class="at-sub">ontem ${int(i.ontem)}</div></div>`).join("")}</div>`;
    } catch (x) { /* */ }
  }
  setInterval(tick, 15000);
  window.AtendidosHoje = { atualizar: tick };
  document.addEventListener("click", () => setTimeout(tick, 50));
  tick();
})();
