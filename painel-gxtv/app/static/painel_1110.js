/* PAINEL_1110 — Visão geral, Vendas (+funil), Saúde e o sininho de alertas.
   Dados: /api/p11/vendas, /api/p11/saude, /api/p11/alertas (arquivos locais da VPS; zero API DataCrazy).
   Sininho: pergunta a cada 20 s (leve, um JSON pequeno). */
(function () {
  const $ = (s, r) => (r || document).querySelector(s);
  const e = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const int = (n) => (Number(n) || 0).toLocaleString("pt-BR");
  const brl = (v) => v == null ? "—" : "R$ " + Number(v).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const brl0 = (v) => v == null ? "—" : "R$ " + Math.round(Number(v)).toLocaleString("pt-BR");
  const pct = (a, b) => b ? Math.round((a / b) * 100) + "%" : "—";
  const usd = (v) => v == null ? "—" : "US$ " + Number(v).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  async function get(url) {
    const r = await fetch(url, { cache: "no-store" });
    if (r.status === 401) { if (window.voltarAoLogin) voltarAoLogin("Sua sessão terminou. Entre de novo."); throw new Error("401"); }
    return r.json();
  }
  function delta(a, b, dinheiro) {
    if (b == null) return "";
    const d = a - b;
    const txt = (d >= 0 ? "+" : "−") + (dinheiro ? brl0(Math.abs(d)) : int(Math.abs(d)));
    return `<span class="p11-d ${d >= 0 ? "bom" : "ruim"}">${txt}</span>`;
  }
  const kpi = (rot, val, sub, cls, spark) => `<article class="p11-kpi ${cls || ""}"><div class="p11-kpi-head"><span class="p11-rot">${rot}</span><span class="p11-spark" ${spark ? `data-spark="${spark}"` : ""}></span></div><div class="p11-big num">${val}</div><div class="p11-sub">${sub || ""}</div></article>`;

  // ------------------------------------------------------------ alertas (sininho)
  const ICONE = { venda: "💰", parado: "⏳", erro: "⚠️" };
  let alertas = [], vistoTs = null, primeira = true;
  try { vistoTs = localStorage.getItem("p11_visto"); } catch (x) { /* */ }
  function naoLidos() { return alertas.filter((a) => !vistoTs || a.ts > vistoTs); }
  function itemAlerta(a) {
    const h = a.ts.slice(11, 16);
    return `<div class="p11-al ${a.nivel}${!vistoTs || a.ts > vistoTs ? " novo" : ""}"><span class="p11-al-ic">${ICONE[a.tipo] || "•"}</span>
      <div><b>${e(a.titulo)}</b><small>${e(a.detalhe)}</small></div><span class="p11-al-h">${h}</span></div>`;
  }
  function desenharSino() {
    const n = naoLidos().length;
    const b = $("#p11Badge");
    if (b) { b.textContent = n > 99 ? "99+" : String(n); b.hidden = !n; }
    const lista = $("#p11SinoLista");
    if (lista && !$("#p11Sino").hidden) lista.innerHTML = alertas.length ? alertas.slice(0, 30).map(itemAlerta).join("") : `<p class="p11-mudo">Nada nas últimas 24 h.</p>`;
    document.title = (n ? `(${n}) ` : "") + "Painel GXTV";
    const g = $("#p11GeralAlertas");
    if (g) g.innerHTML = alertas.length ? alertas.slice(0, 6).map(itemAlerta).join("") : `<p class="p11-mudo">Nada nas últimas 24 h.</p>`;
  }
  function toast(a) {
    const box = $("#p11Toasts");
    if (!box) return;
    const d = document.createElement("div");
    d.className = "p11-toast " + a.nivel;
    d.innerHTML = `<span>${ICONE[a.tipo] || "•"}</span><div><b>${e(a.titulo)}</b><small>${e(a.detalhe)}</small></div>`;
    box.appendChild(d);
    setTimeout(() => d.remove(), 9000);
    try { if (document.hidden && "Notification" in window && Notification.permission === "granted") new Notification(a.titulo, { body: a.detalhe }); } catch (x) { /* */ }
  }
  let ids = new Set();
  async function puxarAlertas() {
    try {
      const j = await get("/api/p11/alertas");
      const novos = j.alertas.filter((a) => !ids.has(a.id));
      ids = new Set(j.alertas.map((a) => a.id));
      alertas = j.alertas;
      if (!vistoTs) { vistoTs = j.agora; try { localStorage.setItem("p11_visto", vistoTs); } catch (x) { /* */ } }
      if (!primeira) novos.filter((a) => a.ts > vistoTs).slice(0, 3).forEach(toast);
      primeira = false;
      desenharSino();
    } catch (x) { /* tenta de novo no próximo ciclo */ }
  }
  function ligarSino() {
    const btn = $("#btnSino"), pop = $("#p11Sino");
    if (!btn || btn.dataset.ok) return;
    btn.dataset.ok = "1";
    btn.addEventListener("click", (ev) => {
      ev.stopPropagation();
      pop.hidden = !pop.hidden;
      if (!pop.hidden) {
        desenharSino();
        vistoTs = alertas.length ? alertas[0].ts : vistoTs;
        try { localStorage.setItem("p11_visto", vistoTs); } catch (x) { /* */ }
        setTimeout(desenharSino, 2500);
        try { if ("Notification" in window && Notification.permission === "default") Notification.requestPermission(); } catch (x) { /* */ }
      }
    });
    document.addEventListener("click", (ev) => { if (!pop.hidden && !pop.contains(ev.target)) pop.hidden = true; });
    puxarAlertas();
    setInterval(puxarAlertas, 20000);
  }

  // ------------------------------------------------------------ visão geral
  async function geral() {
    const box = $("#geral-corpo");
    if (!box) return;
    if (!box.dataset.pronto) {
      box.dataset.pronto = "1";
      box.innerHTML = `<div class="p11-kpis" id="p11GeralKpis"><p class="p11-mudo">Carregando…</p></div>
        <div class="p11-card"><div class="p11-topo"><h3>Alertas (24 h)</h3><span class="p11-mudo">o sininho lá em cima avisa na hora</span></div><div id="p11GeralAlertas"></div></div>`;
    }
    desenharSino();
    try {
      const [v, s] = await Promise.all([get("/api/p11/vendas?periodo=hoje"), get("/api/p11/saude")]);
      const r = v.resumo, o = v.comparacao.ontem || {}, f = v.funil.total;
      const caidos = s.servicos.filter((x) => x.estado !== "active");
      const fi = s.fiscal || {};
      $("#p11GeralKpis").innerHTML =
        kpi("Vendido hoje", brl0(r.reais), `${int(r.n)} pagamentos · ontem ${brl0(o.reais)} ${delta(r.reais, o.reais, true)}`, "", "vendas") +
        kpi("Vendas novas", int(r.novas), `${brl0(r.novas_reais)} ${delta(r.novas, o.novas, false)}`, "", "novas") +
        kpi("Leads → pagaram", `${int(f.leads)} → ${int(f.pagou)}`, `${int(f.teste)} ganharam teste · conversão ${pct(f.pagou, f.leads)}`) +
        kpi("Comprovante parado", int(fi.parados_hoje), `alertas do vigia hoje · ${int(fi.manual_hoje)} foram pro manual`, fi.parados_hoje ? "atencao" : "") +
        kpi("Robô e fiscal", caidos.length ? `${caidos.length} fora` : "tudo de pé", caidos.length ? e(caidos.map((x) => x.rotulo).join(", ")) : `fiscal responde em ~${fi.fast_wh_mediana_s == null ? "—" : fi.fast_wh_mediana_s + " s"}`, caidos.length ? "ruim" : "bom") +
        kpi("IA hoje", usd(s.ia && s.ia.hoje_usd), s.ia && s.ia.saldo ? `saldo ${usd(s.ia.saldo.restante_usd)}` : `média 7 dias ${usd(s.ia && s.ia.media_7d_usd)}`);
    } catch (x) { /* mantém o que tinha */ }
  }

  // ------------------------------------------------------------ vendas + funil
  let periodoV = "hoje";
  try { periodoV = localStorage.getItem("p11_periodo") || "hoje"; } catch (x) { /* */ }
  function barras(b) {
    const max = Math.max(1, ...b.n, ...(b.n_dia_anterior || []));
    const col = b.n.map((v, i) => {
      const fut = b.tipo === "hora" && i > b.hora_agora;
      const ref = b.n_dia_anterior ? `<i class="ref" style="height:${(b.n_dia_anterior[i] / max) * 100}%"></i>` : "";
      return `<div class="p11-col${fut ? " fut" : ""}" title="${e(b.rotulos[i])}: ${int(v)} · ${brl(b.reais[i])}${b.n_dia_anterior ? " · dia anterior " + int(b.n_dia_anterior[i]) : ""}">${ref}<i class="val" style="height:${fut ? 0 : (v / max) * 100}%"></i>${b.tipo === "dia" || i % 3 === 0 ? `<span>${e(b.rotulos[i])}</span>` : ""}</div>`;
    }).join("");
    return `<div class="p11-barras">${col}</div>${b.n_dia_anterior ? `<p class="p11-mudo"><i class="p11-leg val"></i> pagamentos ${periodoV === "hoje" ? "hoje" : "no dia"} <i class="p11-leg ref"></i> dia anterior</p>` : ""}`;
  }
  function funilHtml(f) {
    const t = f.total;
    const nums = f.por_numero.map((n) => `<tr><td>${e(n.numero)}</td><td>${int(n.leads)}</td><td>${int(n.teste)} <small>${pct(n.teste, n.leads)}</small></td><td>${int(n.pagou)} <small>${pct(n.pagou, n.teste)}</small></td><td>${int(n.cadastro)}</td></tr>`).join("");
    const vaza = f.maior_vazamento ? `<span class="p11-vaza">Vaza mais em: <b>${e(f.maior_vazamento)}</b> (${Math.round(f.taxa_vazamento * 100)}% passam)</span>` : "";
    return `<div class="p11-card"><div class="p11-topo"><h3>Por WhatsApp</h3>${vaza}</div>
      ${nums ? `<table class="p11-tab"><thead><tr><th>Número</th><th>Leads</th><th>Teste</th><th>Pagou</th><th>Cadastro</th></tr></thead><tbody>${nums}</tbody></table>` : `<p class="p11-mudo">sem dado por WhatsApp</p>`}
      <p class="p11-mudo">${e(f.nota)}${t.cadastro_sem_dado ? ` ${int(t.cadastro_sem_dado)} ainda sem consulta.` : ""} O desenho das etapas está no gráfico acima.</p></div>`;
  }
  async function vendas() {
    const box = $("#vendas-corpo");
    if (!box) return;
    if (!box.dataset.pronto) {
      box.dataset.pronto = "1";
      box.addEventListener("click", (ev) => {
        const b = ev.target.closest("[data-p11p]");
        if (!b) return;
        periodoV = b.dataset.p11p;
        try { localStorage.setItem("p11_periodo", periodoV); } catch (x) { /* */ }
        vendas();
      });
    }
    let v;
    try { v = await get("/api/p11/vendas?periodo=" + periodoV); } catch (x) { return; }
    const r = v.resumo, c = v.comparacao;
    let comp = "";
    if (v.periodo === "hoje") {
      comp = `Ontem até esta hora ${brl0(c.ontem.reais)} (${int(c.ontem.n)}) ${delta(r.reais, c.ontem.reais, true)} · semana passada ${brl0(c.semana_passada.reais)} · média 7 dias ${brl0(c.media_7d.reais)}.`;
    } else if (v.periodo === "ontem") {
      comp = `Anteontem ${brl0(c.anteontem.reais)} ${delta(r.reais, c.anteontem.reais, true)} · mesmo dia da semana passada ${brl0(c.semana_passada.reais)}.`;
    } else {
      comp = `7 dias anteriores ${brl0(c["7d_anteriores"].reais)} (${int(c["7d_anteriores"].n)}) ${delta(r.reais, c["7d_anteriores"].reais, true)}.`;
    }
    const nums = (v.por_numero || []).map((n) => `${e(n.numero)} ${brl(n.reais)} (${int(n.n)})`).join(" · ");
    box.innerHTML = `
      <div class="p11-topo"><div class="p11-seg">${[["hoje", "Hoje"], ["ontem", "Ontem"], ["7d", "7 dias"]].map(([k, t]) => `<button type="button" data-p11p="${k}" class="${v.periodo === k ? "on" : ""}">${t}</button>`).join("")}</div>
        <span class="p11-mudo">atualizado ${e(v.agora.slice(11, 16))}</span></div>
      <p class="p11-mudo">No período: ${brl0(r.reais)} em ${int(r.n)} pagamentos. ${comp} A lista de cada Pix está na aba Vendas. O gráfico de hora em hora está na Visão geral.</p>
      <p class="p11-mudo">Por WhatsApp: ${nums || "sem pagamento no período"}.</p>
      ${funilHtml(v.funil)}
      <p class="p11-mudo">Fonte: ${e(v.fonte)}. Cada comprovante conta uma vez.</p>`;
  }

  // ------------------------------------------------------------ saúde
  async function saude() {
    const box = $("#saude-corpo");
    if (!box) return;
    let s;
    try { s = await get("/api/p11/saude"); } catch (x) { return; }
    const sv = s.servicos.map((x) => `<div class="p11-sv ${x.estado === "active" ? "ok" : "ruim"}"><span class="p11-luz"></span><div><b>${e(x.rotulo)}</b><small>${e(x.nome)} · ${x.estado === "active" ? "de pé" : e(x.estado)}${x.detalhe ? " · " + e(x.detalhe) : ""}</small></div></div>`).join("");
    const ia = s.ia || {}, fi = s.fiscal || {}, rb = s.robo || {};
    const saldo = ia.saldo
      ? kpi("Saldo de IA", usd(ia.saldo.restante_usd), `carregado ${usd(ia.saldo.carregado_usd)} em ${e(ia.saldo.em.slice(0, 10))}${ia.saldo.dias_restantes != null ? ` · dá ~${String(ia.saldo.dias_restantes).replace(".", ",")} dias` : ""}`, ia.saldo.restante_usd < 20 ? "ruim" : "")
      : kpi("Saldo de IA", "sem dado", "a OpenAI não informa saldo por API; ver nota abaixo", "sem");
    box.innerHTML = `
      <div class="p11-card"><div class="p11-topo"><h3>Serviços</h3><span class="p11-mudo">${s.todos_ok ? "tudo de pé" : "tem serviço fora"} · ${e(s.agora.slice(11, 16))}</span></div><div class="p11-svs">${sv}</div></div>
      <div class="p11-kpis">
        ${saldo}
        ${kpi("Gasto de IA hoje", usd(ia.hoje_usd), `${int(ia.hoje_chamadas)} chamadas · ontem ${usd(ia.ontem_usd)} · média 7d ${usd(ia.media_7d_usd)}`)}
        ${kpi("Fiscal responde em", fi.fast_wh_mediana_s == null ? "—" : fi.fast_wh_mediana_s + " s", `mediana, últimas 2 h (média ${fi.fast_wh_media_s == null ? "—" : fi.fast_wh_media_s + " s"}) · ${int(fi.fast_wh_ok)} ok, ${int(fi.fast_wh_falhou)} falharam`, fi.fast_wh_falhou > fi.fast_wh_ok * 0.3 ? "atencao" : "")}
        ${kpi("Comprovante → renovado", fi.renov_mediana_min == null ? "—" : String(fi.renov_mediana_min).replace(".", ",") + " min", `mediana hoje, ${int(fi.renov_n)} renovações`)}
        ${kpi("Fila de comprovante", `${int(fi.parados_hoje)} parados`, `alertas do vigia hoje · ${int(fi.manual_hoje)} no manual · ciclo do fiscal ${fi.ciclo ? fi.ciclo.seg + " s às " + e(fi.ciclo.hora) : "—"}`, fi.parados_hoje ? "atencao" : "")}
        ${kpi("Fila do robô", rb.pendentes == null ? "—" : int(rb.pendentes) + " pendentes", rb.hora ? `às ${e(rb.hora)} · fila ${int(rb.fila)} · ocupadas ${int(rb.ocupadas)} · aguardando ${int(rb.aguardando)}` : "")}
      </div>
      ${fi.fila_alerta ? `<p class="p11-aviso">Fiscal avisou ciclo lento: ${e(fi.fila_alerta)}</p>` : ""}
      <p class="p11-mudo">Fontes: systemctl; vigia/vigia.log; ia_uso.jsonl (custo por chamada); fiscal.log (FAST_WH = webhook do comprovante até a resposta do fiscal); usados.jsonl; manual.txt; comprovante_parado.jsonl; live.log (POLL).
      ${ia.saldo ? "" : " Saldo: grave o valor carregado em /var/lib/painel-gxtv/ia_saldo.json ({\"saldo_usd\": 100, \"em\": \"2026-10-11T12:00\"}) que o painel desconta o gasto desde então."}</p>`;
  }

  let timer = null;
  function abrir(qual) {
    clearInterval(timer);
    const f = { geral, vendas, saude }[qual];
    if (!f) return;
    f();
    timer = setInterval(() => { if (!document.hidden) f(); }, qual === "saude" ? 20000 : 45000);
  }
  window.P11 = { abrir, ligarSino, puxarAlertas };
})();
