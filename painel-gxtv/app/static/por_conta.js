/* POR_CONTA_1810 — "Recebido por conta hoje" (desligar: /var/lib/painel-gxtv/por_conta_off). */
(function () {
  const e = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const r$ = (n) => (Number(n) || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  async function tick() {
    const box = document.getElementById("por-conta");
    if (!box) return;
    try {
      const r = await fetch("/api/por-conta", { credentials: "same-origin", cache: "no-store" });
      const J = await r.json();
      if (!J.ok) { box.hidden = true; return; }
      box.hidden = false;
      box.innerHTML = `<div class="card" style="padding:14px;margin:12px 0"><div class="lbl">Recebido por conta hoje <small>(atualizado ${e(J.atualizado)})</small></div>
        <table style="width:100%;border-collapse:collapse;margin-top:8px">${J.contas.map((c) => `<tr title="${e(c.fonte)}"><td>${e(c.conta)}</td><td style="text-align:right">${c.n} Pix</td><td style="text-align:right"><b>${r$(c.reais)}</b></td></tr>`).join("")}
        <tr style="border-top:1px solid #8884"><td><b>Total</b></td><td style="text-align:right">${J.total_n}</td><td style="text-align:right"><b>${r$(J.total_reais)}</b></td></tr></table>
        <p class="foot">Fora (não é venda): ${J.fora.map((f) => `${e(f.hora)} ${r$(f.valor)} (${e(f.motivo)})`).join(" · ") || "nada"}. Renovado sem duplicados: ${J.renovado_n} · ${r$(J.renovado_reais)}.</p></div>`;
    } catch (x) { /* */ }
  }
  setInterval(tick, 30000);
  tick();
})();
