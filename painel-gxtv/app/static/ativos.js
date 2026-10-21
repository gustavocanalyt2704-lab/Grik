/* ATIVOS_REAIS_1210 — aba Ativos reais: só números (/api/ativos-reais). V2_1910: pagou/renovou */
window.AtivosReais = (function () {
  let timer = null;
  const n = (v) => (v == null ? "—" : Number(v).toLocaleString("pt-BR"));
  const NOMES = { P1: "Painel 1", P2: "Painel 2", P3: "Painel 3", P4: "Painel 4", P5: "Painel 5", P6: "Painel 6", ALPHA: "Alpha", PROMO: "Promo 3 telas", JORGE: "Jorge" };
  function v2(d, hora) {
    const ps = d.paineis || [];
    const card = (p) => { const v = p.v2 || {}; return `<div class="ar-card${p.ok === false ? " ar-velho" : ""}">
        <small>${NOMES[p.canon] || p.canon}</small><b>${n(v.sigma)}</b>
        <span class="ar-cinza">${n(v.real)} pagou/renovou registrado · ${n(v.sem_pag_curto)} sem registro vence ≤${d.dias_curto || 35}d · ${n(v.sem_pag_longo)} plano longo</span>
        <span>${n(v.teste)} testes · ${n(p.vencido)} vencidos</span></div>`; };
    const princ = ps.filter((p) => !p.outro).map(card).join("");
    const outros = ps.filter((p) => p.outro).map(card).join("");
    const sem = (d.total_sem_pag_curto || 0) + (d.total_sem_pag_longo || 0);
    return `<div class="ar-topo"><h2>Ativos reais</h2><span class="ar-nota">atualizado ${hora} · renova sozinho a cada ~10 min</span></div>
      <div class="ar-dupla">
        <div class="ar-grande"><small>Ativos no Sigma (sem testes)</small><b>${n(d.total_sigma)}</b>
          <span>P1–P6 · sem testes · sem MaxPlayer · duplicados por telefone contam uma vez · ${n(d.total_testes)} testes à parte</span></div>
        <div class="ar-grande ar-sec"><small>Pagou/renovou registrado</small><b>${n(d.total_reais)}</b>
          <span>${n(sem)} sem registro de pagamento: ${n(d.total_sem_pag_curto)} vencem em até ${d.dias_curto || 35}d · ${n(d.total_sem_pag_longo)} plano longo (provável pagamento antes de 30/09)</span></div>
      </div>
      <div class="ar-grade">${princ}</div>
      <h3 class="ar-sub">Outros painéis <small>(fora do total)</small></h3>
      <div class="ar-grade">${outros}</div>
      <p class="ar-nota">Ativo = ativo no Sigma, vencimento no futuro, não teste. Pagou/renovou = registro nos ledgers (desde 30/09). Teste = teste no Sigma ou "Teste Nh criado pelo robô" sem pagamento. Duplicados por telefone contam uma vez. ${d.barrado ? "O Sigma barrou a última passada; painéis apagados mostram o número anterior." : ""}</p>`;
  }
  async function atualizar() {
    const box = document.getElementById("ativos-corpo");
    if (!box) return;
    let d;
    try { const r = await fetch("/api/ativos-reais", { cache: "no-store" }); d = await r.json(); } catch (e) { d = null; }
    if (!d || !d.ok) { box.innerHTML = `<p class="ar-nota">${d && d.motivo ? d.motivo : "Sem dado ainda — a primeira contagem leva alguns minutos."}</p>`; return; }
    const hora = d.gerado ? new Date(d.gerado * 1000).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }) : "—";
    if (d.versao === 2) { box.innerHTML = v2(d, hora); return; }
    const cards = (d.paineis || []).map((p) => `<div class="ar-card${p.ok === false ? " ar-velho" : ""}">
        <small>${NOMES[p.canon] || p.canon}</small><b>${n(p.real)}</b>
        <span>${n(p.teste)} em teste · ${n(p.vencido)} vencidos</span></div>`).join("");
    box.innerHTML = `<div class="ar-topo"><h2>Ativos reais</h2><span class="ar-nota">atualizado ${hora} · renova sozinho a cada ~10 min${d.duracao_s ? ` · última contagem levou ${Math.round(d.duracao_s / 60)} min` : ""}</span></div>
      <div class="ar-grande"><small>Total de ativos reais</small><b>${n(d.total_reais)}</b>
        <span>sem testes · ${n(d.total_testes)} testes ativos à parte · ${n(d.total_vencidos)} vencidos (não renovaram)</span></div>
      <div class="ar-grade">${cards}</div>
      <p class="ar-nota">Ativo real = vencimento ainda não passou e não é teste no Sigma (já pagou ou renovou). ${d.barrado ? "O Sigma barrou a última passada; painéis apagados mostram o número anterior." : ""}</p>`;
  }
  return {
    abrir() { atualizar(); clearInterval(timer); timer = setInterval(atualizar, 60000); },
    fechar() { clearInterval(timer); timer = null; },
  };
})();
