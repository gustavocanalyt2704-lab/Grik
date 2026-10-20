const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const F = {
  brl: (v) => "R$ " + Math.round(v).toLocaleString("pt-BR"),
  brlC: (v) => "R$ " + Number(v).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
  int: (v) => Math.round(v).toLocaleString("pt-BR"),
};
let estado = null;
let vista = "inicio";
let fonte;
const visto = new Set();
const tweens = new WeakMap();

function faltaTxt(seg) {
  if (seg == null || Number.isNaN(seg)) return "sem horário marcado";
  if (seg < 5) return "agora";
  seg = Math.round(seg);
  if (seg < 60) return `falta ${seg}s`;
  const min = Math.floor(seg / 60);
  if (min < 60) return `falta ${min}min`;
  const h = Math.floor(min / 60);
  return `falta ${h}h ${String(min % 60).padStart(2, "0")}min`;
}
function haTxt(epoch) {
  if (!epoch) return "ainda não rodou";
  const s = Date.now() / 1000 - epoch;
  if (s < 90) return "rodou agora";
  if (s < 3600) return `rodou há ${Math.round(s / 60)} min`;
  if (s < 86400) return `rodou há ${Math.floor(s / 3600)} h`;
  return `rodou há ${Math.floor(s / 86400)} dias`;
}
function animateNumber(el, to, fmt) {
  if (to == null || Number.isNaN(to)) {
    el.textContent = "—";
    el._v = null;
    return;
  }
  const from = el._v;
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (from == null || reduced || from === to) {
    el._v = to;
    el.textContent = fmt(to);
    return;
  }
  const t0 = performance.now();
  cancelAnimationFrame(tweens.get(el) || 0);
  el.classList.remove("flash-up", "flash-down");
  void el.offsetWidth;
  el.classList.add(to > from ? "flash-up" : "flash-down");
  const step = (t) => {
    const k = Math.min(1, (t - t0) / 700);
    const e = 1 - Math.pow(1 - k, 3);
    const v = from + (to - from) * e;
    el.textContent = fmt(v);
    el._v = v;
    if (k < 1) tweens.set(el, requestAnimationFrame(step));
    else { el._v = to; el.textContent = fmt(to); }
  };
  tweens.set(el, requestAnimationFrame(step));
}
function tomClasse(el, tom) {
  el.classList.remove("tom-ok", "tom-atencao", "tom-ruim", "tom-sem");
  el.classList.add("tom-" + (tom || "sem"));
}

function render() {
  if (!estado) return;
  const frase = $("#frase");
  frase.textContent = estado.frase || "";
  frase.className = "frase " + (estado.tom || "");
  $("#fraseChats").textContent = (estado.chats && estado.chats.resumo) || "";
  $("#fraseChats").className = "frase " + (estado.tom || "");
  const d = estado.destaques || {};
  pintarDinheiro(d.dinheiro || {});
  pintarPrevisao(d.previsao || {});
  pintarCard($("#cardRenov"), $("#renovVal"), $("#renovFrase"), d.renov, F.int);
  pintarDelta($("#renovDelta"), d.renov);
  pintarCard($("#cardAtend"), $("#atendVal"), null, d.atendidos, F.int);
  pintarDelta($("#atendDelta"), d.atendidos);
  $("#atendQuem").innerHTML = ((d.atendidos || {}).quem || []).map((q) => `<span>${esc(q)}</span>`).join("") || `<span>${esc((d.atendidos || {}).frase || "")}</span>`;
  pintarCard($("#cardSemResp"), $("#semRespVal"), $("#semRespFrase"), d.sem_resposta, F.int);  // INICIO_0810 (no lugar do "Esperando")
  if (window.InicioExtra) InicioExtra.render(estado);
  pintarCard($("#cardVencem"), $("#venceVal"), $("#venceFrase"), d.vencem, F.int);
  pintarVencem(d.vencem || {});
  pintarCalor(estado.calor || {});
  pintarLinha(estado.linha || []);
  pintarRotinas(estado.rotinas || [], estado.rotinas_motivo);
  const pc = $("#atalhoPc");
  const saude = (estado.gavetas || {}).saude || {};
  pc.style.color = (saude.disco >= 80 || saude.cpu >= 85 || saude.robo === false) ? "var(--red)" : "";
  if (vista === "chats") renderChats();
  if (!$("#gaveta").hidden) abrir($("#gaveta").dataset.qual, false);
}

function pintarDinheiro(d) {
  animateNumber($("#moneyBig"), d.v, F.brlC);
  $("#moneyFrase").textContent = d.frase || "";
  const ontem = d.ontem;
  let pct = 0;
  let centro = "—";
  let lbl = "de ontem";
  let cor = "#22d3ee";
  const prev = ((estado.destaques || {}).previsao || {}).v;
  if (d.v == null) { lbl = "sem dado"; }
  else if (prev && prev > 0) {
    pct = Math.min(100, (d.v / prev) * 100);
    centro = Math.round(pct) + "%";
    lbl = "do previsto";
    cor = "#22d3ee";
  } else if (ontem) {
    const razao = d.v / ontem;
    pct = Math.min(100, razao * 100);
    centro = razao >= 10 ? Math.round(razao) + "×" : String(Math.round(razao * 10) / 10).replace(".", ",") + "×";
    cor = razao >= 1 ? "#34d399" : razao >= 0.5 ? "#fbbf24" : "#f87171";
  } else if (d.v) {
    pct = 70;
    centro = "—";
    lbl = "sem ontem";
  }
  const C = 2 * Math.PI * 52;
  const arco = $("#ringArc");
  arco.setAttribute("stroke", cor);
  arco.setAttribute("stroke-dasharray", (C * pct) / 100 + " " + C);
  $("#ringPct").textContent = centro;
  $("#ringLbl").textContent = lbl;
}
function pintarCard(card, valEl, fraseEl, d, fmt) {
  if (!d) return;
  tomClasse(card, d.tom || (d.v == null ? "sem" : "ok"));
  animateNumber(valEl, d.v, fmt);
  if (fraseEl) fraseEl.textContent = d.aviso ? `${d.frase}. ${d.aviso}` : (d.frase || "");
}
function pintarDelta(el, d) {
  const dl = d && d.delta;
  if (!dl) { el.textContent = ""; el.className = "delta"; return; }
  el.textContent = `${dl.txt} vs ontem`;
  el.className = "delta " + (dl.bom ? "bom" : "ruim");
}
function pintarPrevisao(p) {
  $("#prevFrase").textContent = p.v == null ? (p.frase || "sem dado") : `no ritmo atual, fecha o dia com ~${F.brl(p.v)}`;
  $("#prevNota").textContent = p.nota || "";
  const h = p.horas || [];
  const max = Math.max(...h.map((v) => v || 0), 1);
  const agora = horaDoEstado();
  $("#prevBarras").innerHTML = h.map((v, i) => `<i class="${i === agora ? "agora" : ""}${v == null ? " futuro" : ""}" style="height:${v == null ? 3 : Math.max(3, (v / max) * 28)}px" title="${i}h: ${v == null ? "" : F.brl(v)}"></i>`).join("");
}
function fraseAmanha(n) {
  if (n == null) return "";
  return n === 1 ? "1 vence amanhã" : `${F.int(n)} vencem amanhã`;
}
function pintarVencem(v) {
  const host = $("#venceBarra");
  if (v.exato) {
    host.innerHTML = "";
    const partes = [];
    if (v.amanha != null) partes.push(fraseAmanha(v.amanha));
    if (v.aviso) partes.push(v.aviso);
    $("#venceFrase").textContent = partes.join(" · ") || v.frase || "";
    return;
  }
  if (v.v == null || !v.v) { host.innerHTML = ""; return; }
  const ja = Math.min(v.ja_renovaram || 0, v.v);
  host.innerHTML = `<div class="mb"><i class="ok" style="width:${(ja / v.v) * 100}%"></i></div><small>${esc(F.int(ja))} já renovaram · ${esc(F.int(v.v - ja))} faltam</small>`;
  $("#venceFrase").textContent = v.amanha != null ? `${F.int(v.amanha)} recebem aviso de amanhã` : (v.frase || "");
}
function horaDoEstado() {
  const m = String((estado && estado.hora) || "").match(/T(\d{2})/);
  return m ? Number(m[1]) : new Date().getHours();
}
function hhmm(iso) {
  const m = String(iso || "").match(/T(\d{2}):(\d{2})/);
  return m ? `${m[1]}:${m[2]}` : "";
}
function tomEvento(tom) {
  if (tom === "dinheiro" || tom === "novo" || tom === "ok") return "ok";
  if (tom === "ruim" || tom === "erro") return "ruim";
  if (tom === "atencao" || tom === "espera") return "atencao";
  return "ok";
}
function pintarCalor(c) {
  $("#calorTitulo").textContent = c.titulo || "Quando o movimento acontece";
  $("#calorFrase").textContent = c.frase || "";
  const host = $("#calor");
  const horas = c.horas;
  if (!horas) { host.innerHTML = `<p class="vazio">${esc(c.motivo || "sem dado")}</p>`; return; }
  const agora = horaDoEstado();
  const max = Math.max(...horas.map((n, i) => (i <= agora ? n || 0 : 0)), 1);
  const barras = horas.map((n, i) => {
    const futuro = i > agora;
    const valor = futuro ? 0 : (n || 0);
    const pico = c.pico === i && valor > 0;
    const alt = futuro ? 4 : Math.max(6, (valor / max) * 72);
    const cls = `${pico ? "pico" : ""} ${i === agora ? "agora" : ""} ${futuro ? "futuro" : ""}`;
    return `<i class="${cls}" title="${i}h" style="height:${alt}px;opacity:${futuro ? 0.12 : 0.35 + (valor / max) * 0.65}"></i>`;
  }).join("");
  host.innerHTML = `<div class="calor-bars">${barras}</div><div class="calor-eixo"><span>0h</span><span>6h</span><span>12h</span><span>18h</span><span>23h</span></div>`;
}
function pintarLinha(itens) {
  const host = $("#linha");
  if (!itens.length) { host.innerHTML = `<p class="vazio">Nada novo por enquanto.</p>`; return; }
  host.innerHTML = itens.slice(0, 4).map((ev) => {
    const extra = ev.valor ? " · " + F.brlC(ev.valor) : "";
    return `<div class="trilho"><span class="lamp ${tomEvento(ev.tom)}"></span><span class="hora">${esc(hhmm(ev.em))}</span><span class="oque">${esc(ev.titulo || "")}${esc(extra)}</span></div>`;
  }).join("");
}
function pintarRotinas(lista, motivo) {
  const host = $("#rotinaLista");
  const ver = $("#verRotinas");
  if (motivo) { host.innerHTML = `<p class="vazio">${esc(motivo)}</p>`; ver.hidden = true; return; }
  if (!lista.length) { host.innerHTML = `<p class="vazio">Nenhuma rotina agendada apareceu.</p>`; ver.hidden = true; return; }
  const rel = lista.filter((r) => r.relevante);
  host.innerHTML = (rel.length ? rel : lista).slice(0, 4).map(rotinaHtml).join("");
  ver.hidden = lista.length <= 4;
}
function anel(parte, total, cor, centro, rotulo) {
  const C = 2 * Math.PI * 40, pct = total ? Math.min(1, parte / total) : 0;
  return `<div class="anel"><svg viewBox="0 0 100 100"><circle cx="50" cy="50" r="40" fill="none" stroke="var(--surface-2)" stroke-width="12"/><circle cx="50" cy="50" r="40" fill="none" stroke="${cor}" stroke-width="12" stroke-linecap="round" stroke-dasharray="${C * pct} ${C}" transform="rotate(-90 50 50)"/></svg><div class="c"><b>${esc(centro)}</b><span>${esc(rotulo)}</span></div></div>`;
}
function rotinaHtml(r) {
  const res = r.resultado === "ok" ? "deu certo" : r.resultado === "falhou" ? "falhou" : "sem confirmação";
  const lamp = r.resultado === "ok" ? "ok" : r.resultado === "falhou" ? "ruim" : "";
  return `<div class="rot-item${r.perto ? " perto" : ""}">
    <div class="nome">${esc(r.nome)} ${r.sem_descricao ? '<span class="selo">sem descrição</span>' : ""}</div>
    <div class="eta" data-epoch="${r.proxima_em || ""}">${esc(faltaTxt(r.proxima_em ? r.proxima_em - Date.now() / 1000 : null))}</div>
    <div class="sub"><span class="lamp ${lamp}"></span><span>${res}</span><span>${esc(haTxt(r.ultima_em))}</span>${r.sem_descricao ? `<span>${esc(r.tecnico)}</span>` : ""}</div>
  </div>`;
}

function renderChats() {
  const c = estado.chats || {};
  const host = $("#chatsCorpo");
  const pessoas = c.pessoas || [];
  const comNumero = pessoas.filter((p) => p.conversas != null);
  const max = Math.max(...comNumero.map((p) => p.conversas || 0), 1);
  const frases = pessoas.map((p) => `<p>${esc(p.nome)} — ${esc(p.frase || "sem dado")}</p>`).join("");
  const pessoasBloco = comNumero.length
    ? `<div class="bolhas">${comNumero.map((p) => {
        const tam = 96 + Math.sqrt((p.conversas || 0) / max) * 64;
        return `<div class="bolha" style="width:${tam}px;height:${tam}px" title="${esc(p.frase || "")}"><b>${esc(F.int(p.conversas))}</b><span>${esc(p.nome)}</span></div>`;
      }).join("")}</div><details class="resumo-tg"><summary>Frase de cada pessoa</summary>${frases}</details>`
    : `<p class="vazio">sem dado — ainda não deu para separar quem atendeu hoje</p><details class="resumo-tg"><summary>Ver cada pessoa</summary>${frases}</details>`;
  const recentes = c.recentes;
  const recentesHtml = !recentes ? `<p class="vazio">${esc(c.recentes_motivo || "sem dado")}</p>`
    : listaRecentes(recentes.slice(0, 4), c.recentes_motivo) + (recentes.length > 4 ? `<details class="resumo-tg"><summary>Ver as outras ${recentes.length - 4}</summary>${listaRecentes(recentes.slice(4), "")}</details>` : "");
  host.innerHTML = `
    <div class="chats-grade">
      <div class="card largo"><h3>Quem atendeu hoje</h3>${pessoasBloco}</div>
      ${caixa("Quais apps os clientes usam", c.apps, c.apps_motivo, c.origem_apps)}
      ${caixaBolhas("Quais aparelhos eles usam", c.aparelhos, c.aparelhos_motivo, c.origem_aparelho)}
      <div class="card largo"><h3>Do que as pessoas falaram hoje</h3>
        ${c.assuntos && c.assuntos.length ? `<div class="tags">${c.assuntos.map((a) => `<span class="tag">${esc(a.nome)} <b>${esc(F.int(a.n))}</b></span>`).join("")}</div>` : `<p class="vazio">${esc(c.assuntos_motivo || "sem dado — ainda não deu para ler os assuntos")}</p>`}
      </div>
      <div class="card largo"><h3>Últimas conversas</h3>${recentesHtml}</div>
      <details class="card largo resumo-tg"><summary>O restante do dia</summary>
        <p>${esc((estado.gavetas.atendimento || {}).abertas_frase || "")}</p>
        <p>${esc((estado.gavetas.atendimento || {}).resolvidas_frase || "")}</p>
        <p>${esc((estado.gavetas.qualidade || {}).seguradas_frase || "")}</p>
        ${motivosHtml(c.travados, "Mensagens seguradas, por motivo")}
        ${motivosHtml(c.erros, "Erros do robô, por tipo")}
        <h3>O que o resumo do Telegram já contou</h3>
        ${(c.telegram || []).map((l) => `<p>${esc(l)}</p>`).join("") || `<p class="vazio">${esc(c.telegram_motivo || "sem dado")}</p>`}
        <p class="nota">Esse resumo é o que o Telegram já manda. O dinheiro grande do início tira a caixinha e a transferência entre contas da empresa.</p>
      </details>
    </div>`;
  drawDonuts();
}
function drawDonuts() {
  const cores = ["#22d3ee", "#a78bfa", "#34d399", "#fbbf24", "#60a5fa", "#f87171"];
  $$("[data-donut]").forEach((host) => {
    let itens = [];
    try { itens = JSON.parse(host.dataset.donut); } catch (e) { return; }
    const total = itens.reduce((a, b) => a + b.n, 0) || 1;
    const R = 52, C = 2 * Math.PI * R;
    let off = 0;
    const arcos = itens.map((it, i) => {
      const len = C * it.n / total;
      const el = `<circle cx="70" cy="70" r="${R}" fill="none" stroke="${cores[i % 6]}" stroke-width="18" stroke-dasharray="${Math.max(0, len - 2)} ${C}" stroke-dashoffset="${-off}"/>`;
      off += len;
      return el;
    }).join("");
    host.innerHTML = `<svg viewBox="0 0 140 140">${arcos}</svg><div class="center"><b>${esc(F.int(total))}</b><span>no total</span></div>`;
  });
}
function caixa(titulo, itens, motivo, origem) {
  if (!itens || !itens.length) return `<div class="card"><h3>${esc(titulo)}</h3><p class="vazio">${esc(motivo || "sem dado")}</p></div>`;
  const total = itens.reduce((a, b) => a + b.n, 0) || 1;
  const cores = ["#22d3ee", "#a78bfa", "#34d399", "#fbbf24", "#60a5fa", "#f87171"];
  return `<div class="card"><h3>${esc(titulo)}</h3><div class="donut-wrap"><div class="donut" data-donut='${esc(JSON.stringify(itens))}'></div><div>${itens.map((it, i) => `<div class="hb"><div class="top"><span><i style="background:${cores[i % 6]};display:inline-block;width:9px;height:9px;border-radius:3px;margin-right:6px"></i>${esc(it.nome)}</span><b>${esc(F.int(it.n))}</b></div></div>`).join("")}${origem ? `<p class="nota">Contado pelo ${esc(origem)}.</p>` : ""}</div></div></div>`;
}
function caixaBolhas(titulo, itens, motivo, origem) {
  if (!itens || !itens.length) return `<div class="card"><h3>${esc(titulo)}</h3><p class="vazio">${esc(motivo || "sem dado")}</p></div>`;
  const max = Math.max(...itens.map((i) => i.n), 1);
  const cores = ["#22d3ee", "#a78bfa", "#34d399", "#fbbf24", "#60a5fa", "#f87171"];
  return `<div class="card"><h3>${esc(titulo)}</h3><div class="bolhas">${itens.map((it, i) => {
    const tam = 78 + Math.sqrt(it.n / max) * 58;
    return `<div class="bolha" style="width:${tam}px;height:${tam}px;border-color:${cores[i % 6]}"><b>${esc(F.int(it.n))}</b><span>${esc(it.nome)}</span></div>`;
  }).join("")}</div>${origem ? `<p class="nota">Contado pelo ${esc(origem)}.</p>` : ""}</div>`;
}
function caixaBarras(titulo, itens, motivo, origem) {
  if (!itens || !itens.length) return `<div class="card"><h3>${esc(titulo)}</h3><p class="vazio">${esc(motivo || "sem dado")}</p></div>`;
  const max = Math.max(...itens.map((i) => i.n), 1);
  return `<div class="card"><h3>${esc(titulo)}</h3>${itens.map((it) => `<div class="hb"><div class="top"><span>${esc(it.nome)}</span><b>${esc(F.int(it.n))}</b></div><div class="track"><div class="fill" style="width:${(it.n / max) * 100}%"></div></div></div>`).join("")}${origem ? `<p class="nota">Contado pelo ${esc(origem)}.</p>` : ""}</div>`;
}
function listaRecentes(itens, motivo) {
  if (!itens) return `<p class="vazio">${esc(motivo || "sem dado")}</p>`;
  if (!itens.length) return `<p class="vazio">Nenhuma conversa recente.</p>`;
  return `<div class="lista-viva">${itens.map((it) => {
    const esperando = it.esperando || (it.min != null && it.min >= 15);
    const whats = it.whats ? `<span class="whats${it.whats === "sem número" ? " mudo" : ""}">${esc(it.whats)}</span>` : "";
    return `<article><span class="avatar">${esc((it.atendente || "?").slice(0, 1))}</span><div><b class="ph">${esc(it.ph)}</b> ${whats}<div class="mini">${esc(it.atendente || "Ainda sem resposta")} · ${esc(it.assunto || "")}</div></div><span class="espera-min${(it.min || 0) >= 20 ? " ruim" : ""}">${esperando ? esc((it.min || 0) + " min") : "respondida"}</span></article>`;
  }).join("")}</div>`;
}
function motivosHtml(itens, titulo) {
  if (!itens) return `<p class="nota">${esc(titulo)}: sem dado</p>`;
  if (!itens.length) return `<p class="nota">${esc(titulo)}: nada hoje.</p>`;
  return `<h3>${esc(titulo)}</h3><div class="tags">${itens.map((it) => `<span class="tag">${esc(it.nome)} <b>${esc(F.int(it.n))}</b></span>`).join("")}</div>`;
}

const GAVETA = {
  dinheiro: (g) => {
    if (g.motivo) return `<p class="vazio">${esc(g.motivo)}</p>`;
    return `<p class="big num">${esc(F.brlC(g.total || 0))}</p><p class="nota">${esc(g.qtd)} pagamentos de clientes. ${esc(g.ticket_frase || "")}</p>
      <p class="nota">${esc(g.renov_frase || "")}</p><p class="nota">${esc(g.novas_frase || "")}</p>
      <p class="nota">${esc(g.nota || "")}${g.excluidos ? " " + esc(g.excluidos) + " movimentações da empresa ficaram de fora." : ""}</p>
      <h3>Dinheiro ao longo do dia</h3><div class="chart" id="chRev"></div>
      <h3>Pagamentos de hoje</h3>${(g.eventos || []).slice(0, 10).map((ev) => `<p class="nota"><b>${esc(ev.titulo)}</b> — ${esc(ev.detalhe || "")}${ev.valor ? " " + esc(F.brlC(ev.valor)) : ""}</p>`).join("") || `<p class="vazio">Nenhum pagamento ainda hoje.</p>`}`;
  },
  vendas: (g) => `<p class="nota">${esc(g.frase_leads || "")}</p><p class="nota">${esc(g.frase_testes || "")}</p><p class="nota">${esc(g.frase_pagou || "")}</p>
    ${g.conversao == null ? "" : `<p class="nota">${esc(String(g.conversao).replace(".", ","))}% de quem chegou acabou pagando.</p>`}
    <h3>Caminho do cliente hoje</h3>${funil(g)}`,
  clientes: (g) => `${g.motivo ? `<p class="vazio">${esc(g.motivo)}</p>` : ""}
    <p class="nota">${g.ativos == null ? esc(g.motivo || "") : esc(F.int(g.ativos) + " clientes com acesso valendo.")}</p>
    <p class="nota">${g.vence_hoje == null ? "" : esc(F.int(g.vence_hoje) + " vencem hoje.")}</p>
    <p class="nota">${g.vence_amanha == null ? "" : esc(F.int(g.vence_amanha) + " vencem amanhã.")}</p>
    <p class="nota">${g.vencidos == null ? "" : esc(F.int(g.vencidos) + " já venceram e ainda não renovaram.")}</p>
    ${g.aviso ? `<p class="nota">${esc(g.aviso)}</p>` : ""}
    <h3>Clientes por painel</h3>${g.paineis ? tagsMapa(g.paineis) : `<p class="vazio">sem dado — o cadastro não diz o painel</p>`}`,
  atendimento: (g) => `<p class="nota">${esc(g.abertas_frase || "")}</p><p class="nota">${esc(estado.destaques.espera.frase || "")}</p>
    <p class="nota">${esc(g.fila_frase || "")}</p><p class="nota">${esc(g.em_atendimento_frase || "")}</p>
    <p class="nota">${g.tmr_txt ? "Tempo médio para responder: " + esc(g.tmr_txt) : esc(g.tmr_motivo || "")}</p>
    <h3>Quem está esperando</h3>${listaRecentes(g.lista, g.esperando_motivo)}`,
  qualidade: (g) => `<p class="nota">${esc(g.resumo || "")}</p><p class="nota">${esc(g.duvidas_frase || "")}</p><p class="nota">${esc(g.seguradas_frase || "")}</p>
    ${g.nota_motivo ? `<p class="nota">${esc(g.nota_motivo)}</p>` : ""}
    ${g.satisfeitos == null ? "" : `<p class="big num">${esc(F.int(g.satisfeitos))}</p><p class="nota">satisfeitos · ${esc(F.int(g.reclamaram || 0))} reclamaram</p>`}`,
  saude: (g) => `${g.motivo ? "" : ""}<p class="nota">${g.robo === true ? "O robô está ligado." : g.robo === false ? "O robô está parado." : esc(g.robo_motivo || "")}</p>
    ${gauge("Uso do computador", g.cpu, 70, 85)}
    ${gauge("Memória", g.ram, 75, 90)}
    ${gauge("Disco", g.disco, 80, 92)}
    <div class="light"><span class="lamp ${tomSaude(g.envios_min, 15, 20)}"></span><div>${esc(g.envios_frase || g.envios_motivo || "")}</div></div>
    <div class="light"><span class="lamp ${tomSaude(g.calma, 1, 5)}"></span><div>${esc(g.calma_frase || g.calma_motivo || "")}</div></div>
    <div class="light"><span class="lamp ${tomSaude(g.lento, 2, 5)}"></span><div>${esc(g.lento_frase || g.lento_motivo || "")}</div></div>
    <div class="light"><span class="lamp ${g.backup_tom || "sem"}"></span><div>${esc(g.backup_txt || g.backup_motivo || "")}</div></div>`,
  rotinas: () => {
    const lista = estado.rotinas || [];
    const rel = lista.filter((r) => r.relevante), outras = lista.filter((r) => !r.relevante);
    if (!lista.length) return `<p class="vazio">${esc(estado.rotinas_motivo || "sem dado")}</p>`;
    return rel.map(rotinaHtml).join("") + (outras.length ? `<details class="resumo-tg"><summary>Rotinas do sistema (${outras.length})</summary>${outras.map(rotinaHtml).join("")}</details>` : "");
  },
  vencem: () => {
    const v = estado.destaques.vencem || {};
    if (v.v == null) return `<p class="vazio">${esc(v.frase || "sem dado")}</p>`;
    const etapas = [["Vencem hoje", v.v, "#fbbf24"], ["Vencem amanhã", v.amanha, "#60a5fa"], ["Vencem em 2 dias", v.dois_dias, "#a78bfa"]];
    const max = Math.max(...etapas.map((e) => e[1] || 0), 1);
    const paineis = Object.entries(v.por_painel || {});
    const maxp = Math.max(...paineis.map((p) => p[1]), 1);
    const titulo = v.exato ? "vencem hoje de verdade" : "receberam hoje o aviso \"vence hoje\"";
    const bloco = v.exato
      ? `<div><p class="big num">${esc(F.int(v.v))}</p><p class="nota">${esc(titulo)}</p>${v.amanha != null ? `<p class="nota">${esc(fraseAmanha(v.amanha))}</p>` : ""}</div>`
      : `<div class="anel-duplo">${anel(v.ja_renovaram || 0, v.v, "#34d399", `${F.int(v.ja_renovaram || 0)}`, "já renovaram")}<div><p class="big num">${esc(F.int(v.v))}</p><p class="nota">${esc(titulo)}</p></div></div>
      <h3>Avisos de vencimento de hoje</h3>${etapas.map(([n, q, c]) => `<div class="hb"><div class="top"><span>${esc(n)}</span><b>${q == null ? "—" : esc(F.int(q))}</b></div><div class="track"><div class="fill" style="width:${((q || 0) / max) * 100}%;background:${c}"></div></div></div>`).join("")}
      <h3>"Vence hoje" por painel</h3><div class="colunas">${paineis.map(([p, n]) => `<div class="col"><b>${esc(F.int(n))}</b><i style="height:${(n / maxp) * 70 + 4}px"></i><span>${esc(p)}</span></div>`).join("")}</div>`;
    return `${bloco}<p class="nota">${esc(v.fonte || "")}</p>${v.aviso ? `<p class="nota">${esc(v.aviso)}</p>` : ""}`;
  },
};
function tagsMapa(mapa) {
  return `<div class="tags">${Object.entries(mapa).map(([n, v]) => `<span class="tag">${esc(n)} <b>${esc(F.int(v))}</b></span>`).join("")}</div>`;
}
function funil(g) {
  const etapas = [["Chegou no WhatsApp", g.leads], ["Pediu um teste", g.testes], ["Recebeu os preços", g.tabela], ["Pagou", g.pagou]];
  if (etapas.every((e) => e[1] == null)) return `<p class="vazio">sem dado — ainda não dá para ver o caminho do cliente</p>`;
  const base = etapas[0][1] || 1;
  const cores = ["#60a5fa", "#22d3ee", "#a78bfa", "#34d399"];
  return etapas.map(([nome, valor], i) => {
    if (valor == null) return `<p class="nota">${esc(nome)}: sem dado</p>`;
    const larg = Math.max(42, 100 * (valor / base));
    return `<div class="f-bar" style="width:${larg}%;background:${cores[i]}"><span>${esc(nome)}</span><span>${esc(F.int(valor))}</span></div>`;
  }).join("");
}
function gauge(nome, valor, aviso, ruim) {
  if (valor == null) return `<p class="nota">${esc(nome)}: sem dado</p>`;
  const cor = valor >= ruim ? "g-bad" : valor >= aviso ? "g-warn" : "g-ok";
  return `<div class="gauge" style="margin:8px 0"><div class="top" style="display:flex;justify-content:space-between"><span>${esc(nome)}</span><b>${esc(F.int(valor))}%</b></div><div class="track"><div class="fill ${cor}" style="width:${Math.min(100, valor)}%"></div></div></div>`;
}
function tomSaude(v, a, r) {
  if (v == null) return "";
  return v >= r ? "ruim" : v >= a ? "atencao" : "ok";
}
function linhaGrafico() {
  const host = $("#chRev");
  const g = estado.gavetas.dinheiro;
  if (!host || !g.horas) return;
  const w = host.clientWidth || 320, h = 200, m = { l: 36, r: 8, t: 10, b: 22 };
  const serie = g.horas.map((v) => v || 0);
  const max = Math.max(...serie, ...(g.ontem_horas || []).map((v) => v || 0), 1);
  const x = (i) => m.l + ((w - m.l - m.r) * i) / 23;
  const y = (v) => m.t + (h - m.t - m.b) * (1 - v / max);
  const path = (arr) => arr.map((v, i) => `${i ? "L" : "M"}${x(i)},${y(v || 0)}`).join(" ");
  host.innerHTML = `<svg viewBox="0 0 ${w} ${h}"><path d="${path(g.ontem_horas || [])}" fill="none" stroke="#5d6c88" stroke-dasharray="5 5"/><path d="${path(serie)}" fill="none" stroke="#22d3ee" stroke-width="2.5"/></svg>`;
}

function abrir(qual, foco = true) {
  const titulos = { dinheiro: "Dinheiro de hoje", vendas: "Vendas de hoje", clientes: "Clientes", atendimento: "Quem está esperando", qualidade: "Qualidade", saude: "Computador", rotinas: "Próximas rotinas", vencem: "Vencimentos" };
  const semGaveta = qual === "rotinas" || qual === "vencem";
  const g = semGaveta ? null : (estado.gavetas || {})[qual];
  if (!semGaveta && !g) return;
  $("#gaveta").hidden = false;
  $("#gaveta").dataset.qual = qual;
  $("#gavetaTitulo").textContent = titulos[qual] || "Detalhe";
  $("#gavetaCorpo").innerHTML = GAVETA[qual](g || {});
  if (qual === "dinheiro") requestAnimationFrame(linhaGrafico);
  if (foco) $("#gavetaFecha").focus();
}
function fechar() { $("#gaveta").hidden = true; }

// INICIO_0810: só sobram estas abas. A aba aberta fica guardada (hash + navegador),
// então se o navegador recarregar a página ao voltar para ela, abre na mesma aba.
const VISTAS = new Set(["inicio", "vendas-nr", "vendas", "mensagens", "saude", "ranking-apps", "ativos"]);  // PAINEL_1110
const VISTA_ANTIGA = { vivo: "mensagens", semana: "mensagens" };
let subMsg = "vivo";
try { subMsg = localStorage.getItem("p11_msg") || "vivo"; } catch (e) { /* */ }
function vistaGuardada() {
  const h = (location.hash || "").slice(1);
  if (VISTA_ANTIGA[h]) { subMsg = h; return "mensagens"; }
  if (VISTAS.has(h)) return h;
  try { const v = localStorage.getItem("painel_vista"); if (VISTAS.has(v)) return v; } catch (e) { /* sem storage */ }
  return "inicio";
}
function mostrar(nome) {
  if (VISTA_ANTIGA[nome]) { subMsg = nome; nome = "mensagens"; }
  if (!VISTAS.has(nome)) nome = "inicio";
  vista = nome;
  try { localStorage.setItem("painel_vista", nome); } catch (e) { /* sem storage */ }
  try { history.replaceState(null, "", nome === "inicio" ? location.pathname : "#" + nome); } catch (e) { /* ignora */ }
  $("#vista-inicio").hidden = nome !== "inicio";
  $("#vista-chats").hidden = nome !== "chats";
  $("#vista-metricas").hidden = nome !== "metricas";
  const la = $("#vista-lote-atencao");
  if (la) la.hidden = nome !== "lote-atencao";
  const acoes = $("#vista-acoes");
  if (acoes) acoes.hidden = nome !== "acoes";
  if (nome === "metricas") Met.abrir();
  if (nome === "lote-atencao" && window.LoteAtencaoMetricas) LoteAtencaoMetricas.atualizar();
  const rk = $("#vista-ranking-apps");
  if (rk) rk.hidden = nome !== "ranking-apps";
  if (nome === "ranking-apps" && window.RankingAppsMetricas) RankingAppsMetricas.atualizar();
  if (nome === "acoes" && window.Acoes) Acoes.abrir();
  const sm = $("#vista-semana");  // SEMANA_1110
  const naMsg = nome === "mensagens";  // PAINEL_1110: Mensagens = Ao vivo (Agora) + Semana
  if (sm) sm.hidden = !(naMsg && subMsg === "semana");
  if (naMsg && subMsg === "semana" && window.SemanaMensagens) SemanaMensagens.atualizar();
  const vv = $("#vista-vivo");  // AO_VIVO_WEBHOOK_0810
  if (vv) vv.hidden = !(naMsg && subMsg !== "semana");
  if (window.Vivo) { if (naMsg && subMsg !== "semana") Vivo.abrir(); else Vivo.fechar(); }
  const sub = $("#p11Subnav");
  { const at = document.getElementById("atendidos-hoje"); if (at) { at.hidden = !naMsg; if (naMsg && window.AtendidosHoje) AtendidosHoje.atualizar(); } }  // ATENDIDOS_1410
  if (sub) { sub.hidden = !naMsg; $$("[data-msg]").forEach((b) => b.classList.toggle("on", (b.dataset.msg === "semana") === (subMsg === "semana"))); }
  const vnr = $("#vista-vendas-nr");  // VENDAS_1110
  if (vnr) vnr.hidden = nome !== "vendas-nr";
  if (window.VendasNR) { if (nome === "vendas-nr") VendasNR.abrir(); else VendasNR.fechar(); }
  const vd = $("#vista-vendas"), sd = $("#vista-saude");
  if (vd) vd.hidden = nome !== "vendas";
  if (sd) sd.hidden = nome !== "saude";
  if (window.P11) P11.abrir({ inicio: "geral", vendas: "vendas", saude: "saude" }[nome] || "");
  document.body.classList.toggle("na-inicio", false);
  const ar = $("#vista-ativos");  // ATIVOS_REAIS_1210
  if (ar) ar.hidden = nome !== "ativos";
  if (window.AtivosReais) { if (nome === "ativos") AtivosReais.abrir(); else AtivosReais.fechar(); }
  $$(".chip").forEach((b) => b.classList.toggle("on", b.dataset.vista === nome));
  if (nome === "chats") { renderChats(); drawDonuts(); }
}

async function boot() {
  const eu = await fetch("/api/eu").catch(() => null);
  if (eu && eu.ok) entrarApp();
  else document.body.classList.remove("booting"), document.body.classList.add("show-login");
}
function entrarApp() {
  document.body.classList.remove("booting", "show-login");
  $("#app").hidden = false;
  document.body.classList.toggle("na-inicio", false);
  conectar();
  if (window.P11) P11.ligarSino();  // PAINEL_1110
  mostrar(vistaGuardada());  // INICIO_0810: volta na aba em que estava
}
// Conexão: um único relógio para a tela inteira e uma única ligação ao vivo.
// Queda curta reconecta sozinha, em silêncio. Só avisa "sem conexão" depois de 30 s sem nada.
const conexao = { ultimo: Date.now(), tentativa: 0, timer: null, relogio: null };
function marcarVivo() {
  conexao.ultimo = Date.now();
  conexao.tentativa = 0;
  document.body.classList.remove("is-stale");
  $("#live").classList.remove("stale");
  $("#liveTxt").textContent = "AO VIVO";
}
function conectar() {
  clearTimeout(conexao.timer);
  if (fonte) { fonte.onerror = null; fonte.close(); }
  conexao.ultimo = Date.now();
  fonte = new EventSource("/api/stream");
  fonte.addEventListener("snapshot", (ev) => {
    marcarVivo();
    const pacote = JSON.parse(ev.data);
    if (pacote.aviso_local) document.body.classList.add("aviso-local");
    estado = pacote.estado;
    render();
  });
  fonte.addEventListener("ping", marcarVivo);
  fonte.onerror = () => {
    if (fonte.readyState === EventSource.CLOSED) reconectar();
  };
  if (!conexao.relogio) conexao.relogio = setInterval(tique, 1000);
}
async function reconectar() {
  clearTimeout(conexao.timer);
  const eu = await fetch("/api/eu").catch(() => null);
  if (eu && eu.status === 401) { voltarAoLogin("Sua sessão terminou. Entre de novo."); return; }
  conexao.tentativa += 1;
  const espera = Math.min(30000, 1000 * Math.pow(2, Math.min(conexao.tentativa, 5)));
  conexao.timer = setTimeout(conectar, espera);
}
function tique() {
  if (document.body.classList.contains("show-login")) return;
  if (Date.now() - conexao.ultimo > 30000) {
    document.body.classList.add("is-stale");
    $("#live").classList.add("stale");
    $("#liveTxt").textContent = "SEM CONEXÃO";
    if (Date.now() - conexao.ultimo > 45000 && (!fonte || fonte.readyState !== EventSource.CONNECTING)) { conexao.ultimo = Date.now() - 30000; reconectar(); }
  }
  $("#clock").textContent = new Date().toLocaleTimeString("pt-BR");
  $$("[data-epoch]").forEach((el) => {
    const epoch = Number(el.dataset.epoch);
    el.textContent = faltaTxt(epoch ? epoch - Date.now() / 1000 : null);
  });
}
function voltarAoLogin(msg) {
  clearTimeout(conexao.timer);
  if (fonte) { fonte.onerror = null; fonte.close(); fonte = null; }
  estado = null;
  $("#loginErr").textContent = msg || "";
  document.body.classList.add("show-login");
}

let enviando = false;
$("#formLogin").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  if (enviando) return;
  enviando = true;
  const botao = $("#formLogin button[type=submit]");
  botao.disabled = true;
  botao.textContent = "Entrando…";
  try {
    const res = await fetch("/api/entrar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ usuario: $("#usuario").value.trim(), senha: $("#senha").value }),
    });
    const corpo = await res.json().catch(() => ({}));
    if (!res.ok) { $("#loginErr").textContent = corpo.mensagem || "Usuário ou senha incorretos."; return; }
    $("#loginErr").textContent = "";
    $("#senha").value = "";
    entrarApp();
  } catch (e) {
    $("#loginErr").textContent = "Não consegui falar com o servidor. Tente de novo.";
  } finally {
    enviando = false;
    botao.disabled = false;
    botao.textContent = "Entrar no painel";
  }
});
$("#btnSair").addEventListener("click", async () => {
  await fetch("/api/sair", { method: "POST" }).catch(() => null);
  voltarAoLogin("");
});
$$("[data-vista]").forEach((b) => b.addEventListener("click", () => mostrar(b.dataset.vista)));
$$("[data-msg]").forEach((b) => b.addEventListener("click", () => { subMsg = b.dataset.msg; try { localStorage.setItem("p11_msg", subMsg); } catch (e) { /* */ } mostrar("mensagens"); }));
$$("[data-abre]").forEach((b) => b.addEventListener("click", () => abrir(b.dataset.abre)));
$("#verRotinas").addEventListener("click", () => abrir("rotinas"));
$("#gavetaFecha").addEventListener("click", fechar);
$("#gavetaFundo").addEventListener("click", fechar);
$("#btnTv").addEventListener("click", () => document.body.classList.toggle("tv"));
addEventListener("keydown", (e) => {
  if (e.key === "Escape") { fechar(); document.body.classList.remove("tv"); }
  if ((e.key === "t" || e.key === "T") && !e.target.matches("input")) document.body.classList.toggle("tv");
});
boot();
