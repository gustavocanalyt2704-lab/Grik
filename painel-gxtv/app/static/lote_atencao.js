/* Bloco ISOLADO — Lote diário de atenção (pós-atendimento).
   Não mexe na aba Métricas geral. Dados: /api/lote-atencao-metricas (JSON local).
   Aplicar depois do conserto bc-8d350dba.
*/
(function () {
  const $ = (s, r) => (r || document).querySelector(s);
  const e = (s) => String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const int = (n) => (Number(n) || 0).toLocaleString("pt-BR");
  const pct = (n) => ((Number(n) || 0) * 100).toFixed(1).replace(".", ",") + "%";
  const delta = (d) => {
    if (d == null || d === 0) return "";
    const s = d > 0 ? "+" + int(d) : int(d);
    const cls = d > 0 ? "la-up" : "la-down";
    return ` <small class="${cls}">${s} vs ontem</small>`;
  };

  const MOTIVOS = [
    ["trocou_app", "Trocou app"],
    ["ia_chamar", "Ia chamar/testar"],
    ["adiou", "Adiou"],
    ["aberto", "Aberto"],
    ["resolvido_feedback", "Resolvido → feedback"],
  ];

  async function carregar(periodo) {
    const r = await fetch(`/api/lote-atencao-metricas?periodo=${encodeURIComponent(periodo)}`);
    if (!r.ok) throw new Error("lote metricas " + r.status);
    return r.json();
  }

  function cartao(titulo, valor, extra) {
    return `<div class="la-card"><div class="la-k">${e(titulo)}</div><div class="la-v">${valor}</div>${extra || ""}</div>`;
  }

  function desenhar(j) {
    const box = $("#lote-atencao-corpo");
    if (!box) return;
    if (j.periodo === "7d") {
      const rows = (j.dias || []).map((d) => {
        const pm = d.por_motivo || {};
        return `<tr>
          <td>${e(d.dia)}</td>
          <td>${int(d.chamados)}</td>
          <td>${int(pm.trocou_app)}</td><td>${int(pm.ia_chamar)}</td><td>${int(pm.adiou)}</td>
          <td>${int(pm.aberto)}</td><td>${int(pm.resolvido_feedback)}</td>
          <td>${pct(d.taxa_resposta)}</td>
          <td>${int(d.feedbacks)}</td>
        </tr>`;
      }).join("");
      box.innerHTML = `<div class="la-wrap">
        <h3>Lote de atenção — últimos 7 dias</h3>
        <table class="la-tab"><thead><tr>
          <th>Dia</th><th>Chamados</th><th>App</th><th>Ia chamar</th><th>Adiou</th><th>Aberto</th><th>Feedback</th><th>Taxa resp.</th><th>Qtd FB</th>
        </tr></thead><tbody>${rows || "<tr><td colspan=9>sem dados</td></tr>"}</tbody></table>
        <p class="la-nota">Fonte local (zero GET). Bloco separado da aba Métricas.</p>
      </div>`;
      return;
    }
    const D = j.dados || {};
    const vs = D.vs_anterior || {};
    const pm = D.por_motivo || {};
    const ft = D.feedback_tipos || {};
    const vsp = vs.por_motivo || {};
    const vsf = vs.feedback_tipos || {};
    const motivoHtml = MOTIVOS.map(([k, lab]) => {
      const v = pm[k] || 0;
      const d = (vsp[k] || {}).delta;
      return cartao(lab, int(v), delta(d));
    }).join("");
    const fbHtml = [
      ["positivo", "Positivos"],
      ["negativo", "Negativos"],
      ["sugestao", "Sugestões (suporte)"],
      ["conteudo", "Sugestões (conteúdo)"],
    ].map(([k, lab]) => cartao(lab, int(ft[k]), delta((vsf[k] || {}).delta))).join("");
    const lista = (D.lista_feedbacks || []).slice(0, 40).map((f) => {
      const nome = f.nome || "—";
      const tel = f.tel_mask || "****";
      const tipos = (f.tipos || []).join(", ");
      return `<li><b>${e(nome)}</b> ${e(tel)} <em>${e(tipos)}</em><br>${e((f.texto || "").slice(0, 240))}</li>`;
    }).join("") || "<li>nenhum feedback neste período</li>";

    box.innerHTML = `<div class="la-wrap">
      <h3>Lote de atenção — ${e(D.dia || j.dia || "")}</h3>
      <div class="la-grid">
        ${cartao("Clientes chamados", int(D.chamados), delta((vs.chamados || {}).delta))}
        ${cartao("Taxa de resposta", pct(D.taxa_resposta), delta((vs.taxa_resposta || {}).delta))}
        ${cartao("Feedbacks", int(D.feedbacks), delta((vs.feedbacks || {}).delta))}
        ${cartao("Reabertos → ajuda", int(D.reabertos_ajuda), delta((vs.reabertos_ajuda || {}).delta))}
      </div>
      <h4>Por motivo</h4>
      <div class="la-grid">${motivoHtml}</div>
      <h4>Feedbacks (positivo × negativo × sugestões)</h4>
      <div class="la-grid">${fbHtml}</div>
      <h4>Lista de feedbacks</h4>
      <ul class="la-lista">${lista}</ul>
      <p class="la-nota">Fonte: private/lote_atencao_metricas/*.json (local). Etiquetas: lote-atencao, lote-*, feedback-*.</p>
    </div>`;
  }

  function bind() {
    const root = $("#vista-lote-atencao");
    if (!root) return;
    const sel = $("#la-periodo");
    const btn = $("#la-atualizar");
    async function go() {
      const p = (sel && sel.value) || "hoje";
      try {
        const j = await carregar(p);
        desenhar(j);
      } catch (err) {
        const box = $("#lote-atencao-corpo");
        if (box) box.innerHTML = `<p class="la-erro">Sem dados ainda (rode o lote em sombra) ou API indisponível.</p>`;
      }
    }
    if (btn) btn.addEventListener("click", go);
    if (sel) sel.addEventListener("change", go);
    // se a vista estiver visível no load
    if (!root.hidden) go();
    // expõe para o app.js trocar de aba
    window.LoteAtencaoMetricas = { atualizar: go, desenhar, carregar };
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bind);
  else bind();
})();
