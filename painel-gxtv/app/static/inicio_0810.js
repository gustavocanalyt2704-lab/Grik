/* INICIO_0810 — Início: financeiro/renovações pelo ledger do fiscal + quem atendeu por número.
   Usa só o estado que já chega pelo /api/stream (nada de chamada nova). */
(function () {
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const int = (n) => (Number(n) || 0).toLocaleString("pt-BR");
  const brl = (v) => "R$ " + (Number(v) || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const brl0 = (v) => "R$ " + Math.round(Number(v) || 0).toLocaleString("pt-BR");
  let ultimo = "";

  function quemHtml(quem, max) {
    if (!quem || !quem.length) return `<span class="ix-mudo">ninguém respondeu ainda hoje</span>`;
    const mostra = quem.slice(0, max || 6);
    return mostra.map(([nome, n]) => `<span class="ix-quem${nome === "Robô" ? " robo" : ""}">${esc(nome)} <b>${int(n)}</b></span>`).join("") +
      (quem.length > mostra.length ? `<span class="ix-mudo">+${quem.length - mostra.length}</span>` : "");
  }
  window.quemAtendeuHtml = quemHtml;

  function financeiro(f) {
    if (!f) return `<div class="ix-card"><p class="ix-mudo">Financeiro: lendo o ledger do fiscal…</p></div>`;
    if (!f.ok) return `<div class="ix-card"><p class="ix-mudo">Financeiro: sem dado — ${esc(f.erro || "não consegui ler o ledger do fiscal")}</p></div>`;
    const maxPlano = Math.max(1, ...f.por_plano.map((p) => p.reais), f.outros.reais || 0);
    const linhas = f.por_plano.map((p) => `<div class="ix-hb${p.n ? "" : " zero"}">
        <span class="ix-hb-nome">${brl(p.valor_plano)}</span>
        <span class="ix-hb-trilho"><i style="width:${(p.reais / maxPlano) * 100}%"></i></span>
        <span class="ix-hb-n">${int(p.n)}×</span><b>${brl(p.reais)}</b></div>`).join("");
    const outrosVal = (f.outros.valores || []).map(([v, n]) => `${brl(Number(v))} ×${n}`).join(" · ");
    const outros = f.outros.n ? `<div class="ix-hb outros"><span class="ix-hb-nome">Outros valores</span>
        <span class="ix-hb-trilho"><i style="width:${(f.outros.reais / maxPlano) * 100}%"></i></span>
        <span class="ix-hb-n">${int(f.outros.n)}×</span><b>${brl(f.outros.reais)}</b></div><p class="ix-nota">${esc(outrosVal)}</p>` : "";
    const h = f.por_hora || [];
    const hmax = Math.max(1, ...h);
    const agora = new Date().getHours();
    const horas = h.map((v, i) => `<i class="${i === agora ? "agora" : ""}${i > agora ? " futuro" : ""}" style="height:${i > agora ? 2 : Math.max(2, (v / hmax) * 70)}px" title="${i}h: ${brl(v)}"></i>`).join("");
    const dur = (f.por_duracao || []).map(([p, n]) => `<span class="ix-quem">${esc(p)} <b>${int(n)}</b></span>`).join("");
    const ult = (f.ultimas || []).map((u) => `<div class="ix-ult"><span>${esc(u.hora)}</span><span>${esc(u.numero)}</span><b>${u.valor == null ? "sem valor" : brl(u.valor)}</b></div>`).join("");
    const kpi = (rot, val, sub) => `<div class="ix-kpi"><div class="ix-rot">${rot}</div><div class="ix-big num">${val}</div><div class="ix-sub">${sub || ""}</div></div>`;
    return `
      <div class="ix-kpis">
        ${kpi("Renovado hoje (R$)", brl(f.reais), `ontem até agora: ${brl(f.ontem_reais)}`)}
        ${kpi("Renovações hoje", int(f.n), `ontem até agora: ${int(f.ontem_n)}`)}
        ${kpi("Ticket médio", f.ticket == null ? "—" : brl(f.ticket), "valor médio por renovação")}
        ${kpi("Plano que mais saiu", (f.por_plano.slice().sort((a, b) => b.n - a.n)[0] || {}).n ? brl(f.por_plano.slice().sort((a, b) => b.n - a.n)[0].valor_plano) : "—", "o valor que mais saiu hoje")}
      </div>
      <div class="ix-duas">
        <div class="ix-card"><h3>Renovações por valor de plano (hoje)</h3>${linhas}${outros}
          ${f.sem_valor ? `<p class="ix-nota">${int(f.sem_valor)} renovação(ões) sem valor no comprovante.</p>` : ""}</div>
        <div class="ix-card"><h3>R$ por hora (hoje)</h3><div class="ix-horas">${horas}</div>
          <div class="ix-eixo"><span>0h</span><span>6h</span><span>12h</span><span>18h</span><span>23h</span></div>
          <h3 class="ix-h3b">Duração do plano</h3><div class="ix-tags">${dur || '<span class="ix-mudo">—</span>'}</div>
          <h3 class="ix-h3b">Últimas renovações</h3>${ult || '<p class="ix-mudo">nenhuma ainda hoje</p>'}</div>
      </div>
      <p class="ix-nota">Fonte: ledger do fiscal neste servidor (renov_ledger.jsonl + usados.jsonl). Cada comprovante conta uma vez. Sem API do DataCrazy.</p>`;
  }

  function numeros(lista) {
    if (!lista || !lista.length) return "";
    const maxR = Math.max(1, ...lista.map((n) => n.renov_reais || 0));
    return lista.map((n) => `<article class="ix-num">
        <header><b>${esc(n.numero)}</b>${n.sem_resposta ? `<span class="ix-alerta">${int(n.sem_resposta)} sem resposta</span>` : ""}</header>
        <div class="ix-num-grade">
          <div><small>Renovações hoje</small><b class="num">${int(n.renov_n)}</b></div>
          <div><small>Renovado (R$)</small><b class="num">${brl0(n.renov_reais)}</b></div>
          <div><small>Clientes que escreveram</small><b class="num">${n.conversas_wh == null ? "—" : int(n.conversas_wh)}</b></div>
          <div><small>Msgs receb. / env.</small><b class="num ix-pq">${n.recebidas_wh == null ? "—" : int(n.recebidas_wh) + " / " + int(n.enviadas_wh)}</b></div>
        </div>
        <div class="ix-barra"><i style="width:${((n.renov_reais || 0) / maxR) * 100}%"></i></div>
        <div class="ix-quem-tit">Quem atendeu (clientes hoje)</div>
        <div class="ix-tags">${quemHtml(n.quem)}${n.sem_atendente ? `<span class="ix-mudo">sem atendente: ${int(n.sem_atendente)}</span>` : ""}${n.robo_proativo ? `<span class="ix-mudo">+${int(n.robo_proativo)} só receberam aviso do robô</span>` : ""}</div>
      </article>`).join("");
  }

  function render(estado) {
    const host = document.getElementById("inicioExtra");
    if (!host || !estado) return;
    const chave = JSON.stringify([estado.financeiro, estado.por_numero, estado.por_numero_ok, new Date().getHours()]);
    if (chave === ultimo) return;
    ultimo = chave;
    const bloco = numeros(estado.por_numero);
    if (!bloco) { host.innerHTML = ""; return; }
    host.innerHTML = `
      <!-- PAINEL_1110: financeiro saiu daqui (está na aba Vendas, sem duplicar) -->
      <section class="ix-bloco"><h2 class="ix-tit">Renovações por WhatsApp</h2>
        <div class="ix-nums">${bloco}</div>
        <p class="ix-nota">Renovações: ledger do fiscal. Clientes e mensagens: registro do webhook. "Quem atendeu" (registro do webhook, em clientes): Robô = clientes que receberam resposta do robô; nomes = atendente atribuído à conversa no DataCrazy (o webhook não registra o que o humano digita). "Sem resposta": espelho (parcial).</p>
      </section>`;
  }
  window.InicioExtra = { render };
})();
