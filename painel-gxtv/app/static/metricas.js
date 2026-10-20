/* Aba Métricas: tudo em gráfico e cartão. Os números vêm de /api/metricas (uma linha por conversa, sem telefone)
   e do resumo do /contagem que já chega no estado ao vivo. Os filtros são aplicados aqui no aparelho. */
const Met = (() => {
  const $m = (s) => document.querySelector(s);
  const e = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const int = (v) => (v == null || Number.isNaN(v) ? "—" : Math.round(v).toLocaleString("pt-BR"));
  const brl = (v) => (v == null ? "—" : "R$ " + Number(v).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
  const pct = (a, b) => (b ? Math.round((a / b) * 100) : 0);
  const COR = ["#22d3ee", "#a78bfa", "#34d399", "#fbbf24", "#60a5fa", "#f87171", "#f472b6", "#2dd4bf", "#fb923c", "#94a3b8"];
  const APPS = {
    "UTRA PLUS": { s: "U+", c: "#ef4444" }, "XCIPTV": { s: "XC", c: "#2563eb" }, "Brasil IPTV": { s: "BR", c: "#16a34a", c2: "#facc15" },
    "Max Player": { s: "MAX", c: "#7c3aed" }, "MN TECH": { s: "MN", c: "#0d9488" }, "Fun Play": { s: "FUN", c: "#db2777" },
    "Flex Player": { s: "FX", c: "#d97706" }, "XP IPTV": { s: "XP", c: "#ea580c" }, "IPTV Smarters": { s: "S", c: "#4f46e5" },
    "Smart STB": { s: "STB", c: "#475569" }, "IBO Player": { s: "IBO", c: "#0891b2" },
  };
  const DEVS = {
    "LG": { i: "i-tv", c: "#a50034" }, "Samsung": { i: "i-tv", c: "#1428a0" }, "Roku": { i: "i-box", c: "#6c3c97" },
    "Fire Stick": { i: "i-stick", c: "#ff9900" }, "TV Box": { i: "i-box", c: "#0ea5e9" }, "Android TV": { i: "i-tv", c: "#3ddc84" },
    "TCL": { i: "i-tv", c: "#e60012" }, "Philco": { i: "i-tv", c: "#1d4ed8" }, "AOC": { i: "i-tv", c: "#334155" }, "Semp": { i: "i-tv", c: "#0f766e" },
    "Celular": { i: "i-phone", c: "#22d3ee" }, "Computador": { i: "i-laptop", c: "#94a3b8" },
  };
  let periodo = "hoje";
  let dados = {};
  let carregando = null;
  let timer = null;
  const filtro = { n: "", at: "", app: "", dev: "" };

  async function carregar(p, forcar) {
    const guardado = dados[p];
    if (!forcar && guardado && Date.now() - guardado._em < 110000) return guardado;
    const r = await fetch(`/api/metricas?periodo=${p}`);
    if (r.status === 401) { if (window.voltarAoLogin) voltarAoLogin("Sua sessão terminou. Entre de novo."); return null; }
    const j = await r.json();
    j._em = Date.now();
    if (j.ok) dados[p] = j;
    return j;
  }
  async function abrir() {
    clearInterval(timer);
    timer = setInterval(() => { if (!$m("#vista-metricas").hidden) atualizar(true); else clearInterval(timer); }, 120000);
    await atualizar(false);
    if (!dados["7d"]) { await carregar("7d").catch(() => null); if (dados[periodo] && !$m("#vista-metricas").hidden) desenhar(dados[periodo]); }
  }
  async function atualizar(forcar) {
    if (carregando) return;
    carregando = carregar(periodo, forcar).catch(() => null);
    const j = await carregando;
    carregando = null;
    if (!j) { $m("#fraseMet").textContent = "Não consegui buscar as métricas agora. Tento de novo em 2 minutos."; return; }
    if (!j.ok) { $m("#fraseMet").textContent = j.motivo || "sem dado"; $m("#metCorpo").innerHTML = ""; setTimeout(() => atualizar(true), 15000); return; }
    opcoes(j);
    desenhar(j);
  }
  function opcoes(j) {
    const conta = (f) => { const c = {}; j.conversas.forEach((r) => f(r).forEach((k) => { if (k) c[k] = (c[k] || 0) + 1; })); return Object.entries(c).sort((a, b) => b[1] - a[1]); };
    const preencher = (sel, lista, todos, chave) => {
      const el = $m(sel);
      const atual = filtro[chave];
      el.innerHTML = `<option value="">${e(todos)}</option>` + lista.map(([k, n]) => `<option value="${e(k)}"${k === atual ? " selected" : ""}>${e(k)} (${int(n)})</option>`).join("");
      el.classList.toggle("on", !!atual);
    };
    preencher("#fNumero", conta((r) => [r.n]), "Números", "n");
    preencher("#fAtendente", conta((r) => Object.keys(r.at || {})), "Atendentes", "at");
    preencher("#fApp", conta((r) => [r.app || "Sem app identificado"]), "Apps", "app");
    preencher("#fAparelho", conta((r) => [r.dev || "Sem aparelho identificado"]), "Aparelhos", "dev");
    $m("#fLimpar").hidden = !Object.values(filtro).some(Boolean);
  }
  function passa(r) {
    if (filtro.n && r.n !== filtro.n) return false;
    if (filtro.at && !(r.at || {})[filtro.at]) return false;
    if (filtro.app && (r.app || "Sem app identificado") !== filtro.app) return false;
    if (filtro.dev && (r.dev || "Sem aparelho identificado") !== filtro.dev) return false;
    return true;
  }
  const med = (a) => { if (!a.length) return null; const s = [...a].sort((x, y) => x - y); const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
  const media = (a) => (a.length ? a.reduce((x, y) => x + y, 0) / a.length : null);
  const pq = (a, p) => { if (!a.length) return null; const s = [...a].sort((x, y) => x - y); return s[Math.min(s.length - 1, Math.ceil(p * s.length) - 1)]; };
  const tempo = (s) => { if (s == null) return "—"; s = Math.round(s); if (s < 60) return `${s} s`; const m = Math.round(s / 60); if (m < 60) return `${m} min`; const h = Math.floor(m / 60); return `${h}h${String(m % 60).padStart(2, "0")}`; };

  function calc(regs) {
    if (!regs) return null;
    const rc = regs.filter((r) => r.rc);
    const atend = regs.filter((r) => r.rc || r.ma);
    const t1 = rc.map((r) => r.t1).filter((v) => v != null);
    const en = rc.flatMap((r) => r.en || []);
    const rs = rc.map((r) => r.rs).filter((v) => v != null);
    const mpc = rc.map((r) => r.mc + r.ma);
    const ne = rc.filter((r) => r.ne);
    const pessoas = {};
    regs.forEach((r) => Object.entries(r.at || {}).forEach(([p, n]) => { const x = (pessoas[p] = pessoas[p] || { conv: 0, msgs: 0, prim: 0, t1: [] }); x.conv++; x.msgs += n; }));
    rc.forEach((r) => { if (r.fr && pessoas[r.fr]) { pessoas[r.fr].prim++; if (r.t1 != null) pessoas[r.fr].t1.push(r.t1); } });
    const cont = (f) => { const c = {}; regs.forEach((r) => [].concat(f(r) || []).forEach((k) => { if (k) c[k] = (c[k] || 0) + 1; })); return Object.entries(c).sort((a, b) => b[1] - a[1]); };
    return {
      regs, rc: rc.length, atend: atend.length, novos: rc.filter((r) => r.nv).length,
      mc: regs.reduce((a, r) => a + r.mc, 0), ma: regs.reduce((a, r) => a + r.ma, 0), mt: regs.reduce((a, r) => a + r.mt, 0),
      so_aviso: regs.filter((r) => !r.rc && !r.ma && r.mt).length,
      mpc_media: media(mpc), mpc_med: med(mpc),
      t1, t1_med: med(t1), t1_media: media(t1), t1_p90: pq(t1, 0.9), t1_p95: pq(t1, 0.95),
      en_med: med(en), en_media: media(en), en_n: en.length, rs_med: med(rs), rs_media: media(rs), rs_n: rs.length,
      ne: ne.length, sr: rc.filter((r) => r.sr).length, ig: rc.filter((r) => r.ig).length, ab: rc.filter((r) => r.ab).length,
      re1: rc.filter((r) => r.re === 1).length, re2: rc.filter((r) => r.re === 2).length, re3: rc.filter((r) => r.re === 3).length,
      nres: ne.filter((r) => !r.re).length, ev: rc.filter((r) => r.ev).length, rb: rc.filter((r) => r.rb).length,
      rh: rc.filter((r) => r.rh).length, hh: rc.filter((r) => r.hh).length, es: regs.filter((r) => r.es).length,
      vi: rc.filter((r) => r.vi).length, rp: rc.filter((r) => r.rp).length, rv: regs.filter((r) => r.rv).length,
      rv_origem: cont((r) => r.rv), cn: rc.filter((r) => r.cn).length, cnr: rc.filter((r) => r.cn === 2).length,
      pb: cont((r) => r.pb), rep: cont((r) => r.rep), pb_conv: rc.filter((r) => (r.pb || []).length).length,
      apps: cont((r) => ((r.rc || r.ma) ? r.app : null)), sem_app: atend.filter((r) => !r.app).length,
      devs: cont((r) => ((r.rc || r.ma) ? r.dev : null)), sem_dev: atend.filter((r) => !r.dev).length,
      ins: cont((r) => r.ins), cr: regs.filter((r) => r.cr).length, testados: cont((r) => (r.ts ? (r.app || "App não identificado") : null)),
      ts: regs.filter((r) => r.ts).length, numeros: cont((r) => (r.rc ? r.n : null)), pessoas,
      horas: (() => { const h = Array(24).fill(0); rc.forEach((r) => (r.hs || []).forEach((x) => h[x]++)); return h; })(),
    };
  }
  function fila(regs, dia) {
    const ev = [];
    regs.forEach((r) => (r.fq || []).forEach(([a, b]) => { if (b - a >= 1) { ev.push([a, 1]); ev.push([b, -1]); } }));
    if (!ev.length) return null;
    ev.sort((x, y) => x[0] - y[0] || x[1] - y[1]);
    let cur = 0, max = 0, quando = null;
    const pontos = {};
    ev.forEach(([t, d]) => { cur += d; const k = Math.floor(t / 15) * 15; pontos[k] = Math.max(pontos[k] || 0, cur); if (cur > max) { max = cur; quando = t; } });
    return { max, quando, pontos };
  }
  const hhmm = (min) => { const d = new Date(min * 60000); return d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", timeZone: "America/Bahia" }); };

  function delta(a, b, menorMelhor) {
    if (a == null || b == null) return "";
    if (b === 0 && a === 0) return `<span class="dl igual">= ontem</span>`;
    const d = a - b;
    if (Math.abs(d) < 1e-9) return `<span class="dl igual">= ${e(rotAntes)}</span>`;
    const p = b ? Math.round((Math.abs(d) / b) * 100) : null;
    const bom = menorMelhor ? d < 0 : d > 0;
    return `<span class="dl ${bom ? "bom" : "ruim"}">${d > 0 ? "▲" : "▼"} ${p == null ? int(Math.abs(d)) : p + "%"}</span>`;
  }
  let rotAntes = "ontem";
  function cartao(icone, cor, rotulo, valor, sub, dl, extra) {
    return `<div class="mc"><span class="mc-ic" style="--c:${cor}"><svg class="i"><use href="#${icone}"/></svg></span><div class="mc-v num">${valor}</div><div class="mc-l">${e(rotulo)}</div>${dl || ""}${sub ? `<div class="mc-s">${sub}</div>` : ""}${extra || ""}</div>`;
  }
  function rosca(itens, centro, rot) {
    const total = itens.reduce((a, b) => a + b[1], 0) || 1;
    const R = 40, C = 2 * Math.PI * R;
    let off = 0;
    const arcos = itens.map(([, n, c], i) => { const l = (C * n) / total; const s = `<circle cx="50" cy="50" r="${R}" fill="none" stroke="${c || COR[i % 10]}" stroke-width="14" stroke-dasharray="${Math.max(0, l - 1.5)} ${C}" stroke-dashoffset="${-off}" transform="rotate(-90 50 50)"/>`; off += l; return s; }).join("");
    return `<div class="rosca"><svg viewBox="0 0 100 100"><circle cx="50" cy="50" r="${R}" fill="none" stroke="var(--surface-2)" stroke-width="14"/>${arcos}</svg><div class="c"><b>${e(centro)}</b><span>${e(rot)}</span></div></div>`;
  }
  function legenda(itens, total) {
    return `<div class="leg">${itens.map(([n, v, c], i) => `<div><i style="background:${c || COR[i % 10]}"></i><span>${e(n)}</span><b>${int(v)}</b>${total ? `<small>${pct(v, total)}%</small>` : ""}</div>`).join("")}</div>`;
  }
  function barras(itens, cor, fmt) {
    if (!itens.length) return `<p class="vazio">nada neste período</p>`;
    const max = Math.max(...itens.map((x) => x[1]), 1);
    return itens.map(([n, v, c], i) => `<div class="hb"><div class="top"><span>${e(n)}</span><b>${fmt ? fmt(v) : int(v)}</b></div><div class="track"><div class="fill" style="width:${(v / max) * 100}%;background:${c || cor || COR[i % 10]}"></div></div></div>`).join("");
  }
  function selo(app) {
    const a = APPS[app] || { s: (app || "?").slice(0, 2).toUpperCase(), c: "#64748b" };
    return `<span class="app-logo" style="background:${a.c2 ? `linear-gradient(135deg,${a.c} 55%,${a.c2} 55%)` : a.c}">${e(a.s)}</span>`;
  }
  function devIc(dev) {
    const d = DEVS[dev] || { i: "i-tv", c: "#64748b" };
    return `<span class="dev-logo" style="--c:${d.c}"><svg class="i"><use href="#${d.i}"/></svg></span>`;
  }
  function blocos(titulo, icone, corpo, classe) {
    return `<section class="card mbloco ${classe || ""}"><h3><svg class="i"><use href="#${icone}"/></svg> ${e(titulo)}</h3>${corpo}</section>`;
  }
  function tempoCard(nome, med_, media_, n, antes, extra) {
    return `<div class="tc"><div class="tc-l">${e(nome)}</div><div class="tc-v num">${tempo(med_)}</div><div class="tc-s">metade em até · média ${tempo(media_)} · ${int(n)} casos</div>${delta(med_, antes, true)}${extra || ""}</div>`;
  }

  function desenhar(j) {
    rotAntes = j.rotulo_antes || "ontem";
    const regs = j.conversas.filter(passa);
    const A = calc(regs);
    const B = j.anteriores ? calc(j.anteriores.filter(passa)) : null;
    const b = (k) => (B ? B[k] : null);
    const filtrado = Object.values(filtro).some(Boolean);
    const compFalta = j.periodo === "hoje" && !B ? " Comparação com ontem: sem dado." : "";
    $m("#fraseMet").innerHTML = `${e(j.rotulo[0].toUpperCase() + j.rotulo.slice(1))}: <b>${int(A.atend)}</b> clientes atendidos, <b>${int(A.rc)}</b> escreveram, <b>${int(A.so_aviso)}</b> só receberam aviso. ${int(A.regs.length)} conversas no período.${B ? ` Setas comparam com ${e(j.rotulo_antes)}.` : compFalta}${j.aviso ? ` <span class="selo-f">${e(j.aviso)}</span>` : ""}${filtrado ? " <span class=\"selo-f\">filtrado</span>" : ""}`;
    const res = estado && estado.resumo_contador;
    const H = [];

    // 1. Volume
    H.push(blocos("Movimento", "i-chat", `<div class="mcs">
      ${cartao("i-chat", "#22d3ee", "conversas recebidas", int(A.rc), `${int(A.so_aviso)} só receberam aviso automático`, delta(A.rc, b("rc")))}
      ${cartao("i-users", "#a78bfa", "clientes atendidos", int(A.atend), "escreveram ou tiveram resposta", delta(A.atend, b("atend")))}
      ${cartao("i-star", "#34d399", "contatos novos", int(A.novos), `${pct(A.novos, A.rc)}% novos · ${pct(A.rc - A.novos, A.rc)}% já conheciam`, delta(A.novos, b("novos")))}
      ${cartao("i-repeat", "#fbbf24", "mensagens por conversa", (A.mpc_med ?? 0).toLocaleString("pt-BR"), `média ${(A.mpc_media || 0).toFixed(1).replace(".", ",")}`, "")}
    </div>
    <div class="dupla">${rosca([["Clientes", A.mc, "#22d3ee"], ["Robô e equipe", A.ma, "#a78bfa"], ["Cobrança automática", A.mt, "#fbbf24"]], int(A.mc + A.ma + A.mt), "mensagens")}
    ${legenda([["Dos clientes", A.mc, "#22d3ee"], ["Do robô e da equipe", A.ma, "#a78bfa"], ["Cobrança automática", A.mt, "#fbbf24"]], A.mc + A.ma + A.mt)}</div>
    <h4>Quando os clientes escreveram</h4>${colunasHora(A.horas)}`));

    // 2. Tempos
    const pior = A.t1_p95;
    H.push(blocos("Tempo de resposta", "i-clock", `<div class="tcs">
      ${tempoCard("1ª resposta", A.t1_med, A.t1_media, A.t1.length, b("t1_med"), `<div class="pp"><span>9 em 10 em até <b>${tempo(A.t1_p90)}</b></span><span>pior 5%: acima de <b>${tempo(pior)}</b></span></div>`)}
      ${tempoCard("Entre uma resposta e outra", A.en_med, A.en_media, A.en_n, b("en_med"))}
      ${tempoCard("Até resolver", A.rs_med, A.rs_media, A.rs_n, b("rs_med"))}
    </div><h4>Quanto tempo o cliente esperou a 1ª resposta</h4>${faixas(A.t1)}`));

    // 3. Resultado
    const resolvidas = A.re1 + A.re2 + A.re3;
    H.push(blocos("Resultado das conversas", "i-check", `<div class="dupla">
      ${rosca([["Resolvidas", resolvidas, "#34d399"], ["Não resolvidas", A.nres, "#f87171"]], `${pct(resolvidas, resolvidas + A.nres)}%`, "resolvidas")}
      ${legenda([["Cliente agradeceu", A.re1, "#34d399"], ["Renovou", A.re2, "#22d3ee"], ["Resposta curta (\"ok\", \"deu certo\")", A.re3, "#2dd4bf"], ["Sem sinal de resolvida", A.nres, "#f87171"]])}
    </div><div class="mcs">
      ${cartao("i-alert", "#fbbf24", "precisavam de resposta", int(A.ne), "", delta(A.ne, b("ne")))}
      ${cartao("i-x", "#f87171", "ficaram sem resposta", int(A.sr), `${pct(A.sr, A.ne)}% das que precisavam`, delta(A.sr, b("sr"), true))}
      ${j.periodo === "hoje" ? cartao("i-hourglass", "#fb923c", "sem retorno há 30+ min", int(A.ig), "a última mensagem do cliente ainda não teve resposta", "") : ""}
      ${cartao("i-arrow", "#94a3b8", "abandonadas", int(A.ab), "respondemos e o cliente sumiu (1h+)", delta(A.ab, b("ab"), true))}
      ${cartao("i-repeat", "#f472b6", "voltaram em 24h", int(A.rb), `de ${int(A.ev)} que agradeceram`, delta(A.rb, b("rb"), true))}
    </div><h4>Passagens de conversa</h4><div class="passes">
      ${passe("i-bot", "Robô", "i-users", "Pessoa", A.rh, "robô passou para uma pessoa")}
      ${passe("i-users", "Pessoa", "i-users", "Outra pessoa", A.hh, "passou de uma pessoa para outra")}
      ${passe("i-bot", "Robô", "i-alert", "Pediu ajuda", A.es, "robô pediu ajuda humana")}
    </div>`));

    // 4. Por atendente
    const pes = Object.entries(A.pessoas).sort((x, y) => y[1].conv - x[1].conv);
    const maxc = Math.max(...pes.map((p) => p[1].conv), 1);
    H.push(blocos("Quem atendeu", "i-users", `<div class="pessoas">${pes.map(([n, p], i) => `<div class="pessoa"><span class="av" style="--c:${n === "Robô" ? "#22d3ee" : COR[(i + 1) % 10]}">${n === "Robô" ? `<svg class="i"><use href="#i-bot"/></svg>` : e(n[0])}</span>
      <div class="pb"><div class="top"><b>${e(n)}</b><span>${int(p.conv)} conversas · ${int(p.msgs)} msgs</span></div><div class="track"><div class="fill" style="width:${(p.conv / maxc) * 100}%;background:${n === "Robô" ? "#22d3ee" : COR[(i + 1) % 10]}"></div></div>
      <div class="mini">respondeu primeiro ${int(p.prim)} vezes${p.t1.length ? ` · metade em até ${tempo(med(p.t1))}` : ""}${B && B.pessoas[n] ? ` · ${delta(p.conv, B.pessoas[n].conv)}` : ""}</div></div></div>`).join("") || `<p class="vazio">ninguém neste filtro</p>`}</div>`));

    // 5. Por número
    H.push(blocos("Por número de WhatsApp", "i-phone", barras(A.numeros.slice(0, 12).map(([n, v]) => [n, v, n === "sem número" || n === "Número não identificado" ? "#475569" : null]), "#60a5fa") + `<p class="nota">Conversas de clientes em cada número. "sem número" = o robô ainda não gravou qual WhatsApp atendeu.</p>`));

    // 6. Vendas e renovações
    const rv = res ? res.renov : {};
    const vd = res ? res.vendas : {};
    const mp = res ? res.mp : null;
    const origemNome = { fiscal_comprovante: "Comprovante conferido sozinho", conferencia_mp_manual: "Conferido à mão", pix: "Pix do robô", conferida: "Conferida" };
    H.push(blocos("Vendas e renovações", "i-money", `<div class="mcs">
      ${cartao("i-funnel", "#a78bfa", "pediram preço / quiseram assinar", int(A.vi), "pela conversa", delta(A.vi, b("vi")))}
      ${cartao("i-repeat", "#22d3ee", "quiseram renovar", int(A.rp), "falaram em renovar, Pix ou comprovante", delta(A.rp, b("rp")))}
      ${cartao("i-check", "#34d399", "conversas de quem renovou", int(A.rv), "um cliente pode ter falado em mais de um número", delta(A.rv, b("rv")))}
      ${cartao("i-x", "#f87171", "falaram em cancelar", int(A.cn), `${int(A.cnr)} desistiram de cancelar`, delta(A.cn, b("cn"), true))}
    </div>
    ${A.rv_origem.length ? `<h4>Como as renovações foram conferidas</h4><div class="dupla">${rosca(A.rv_origem.map(([k, v], i) => [origemNome[k] || k, v, COR[i]]), int(A.rv), "renovações")}${legenda(A.rv_origem.map(([k, v], i) => [origemNome[k] || k, v, COR[i]]), A.rv)}</div>` : ""}
    ${!filtrado && j.periodo === "hoje" && res ? `<h4>Do resumo do Telegram (dia inteiro)</h4><div class="mcs">
      ${cartao("i-money", "#34d399", "pagamentos de clientes", mp && mp.ok ? int(mp.n) : "—", mp && mp.ok ? brl(mp.reais) : "sem dado — o Mercado Pago ainda não chegou", mp && mp.ontem_ok ? delta(mp.n, mp.ontem_n) : "")}
      ${cartao("i-money", "#22d3ee", "renovações conferidas", int(rv.n), brl(rv.reais), delta(rv.n, rv.ontem_n))}
      ${cartao("i-star", "#a78bfa", "vendas novas", (!res.sigma_cadastro_desatualizado && res.sigma_ok && vd.vendas_novas != null) ? int(vd.vendas_novas) : "—", res.sigma_cadastro_desatualizado ? "cadastro Sigma desatualizado — não inventamos o número (MP ≠ venda nova)" : (res.sigma_ok ? "clientes novos pagos hoje" : "sem dado — o cadastro do Sigma ainda não chegou"), (!res.sigma_cadastro_desatualizado && res.sigma_ok && vd.vendas_novas != null) ? delta(vd.vendas_novas, vd.vendas_novas_ontem) : "")}
      ${cartao("i-box", "#2dd4bf", "testes criados", (!res.sigma_cadastro_desatualizado && res.sigma_ok && vd.testes_criados != null) ? int(vd.testes_criados) : int(A.ts), (!res.sigma_cadastro_desatualizado && res.sigma_ok && vd.testes_criados != null) ? "no Sigma" : (res.sigma_cadastro_desatualizado ? "contado pelos testes que o robô criou — cadastro Sigma desatualizado" : "contado pelos testes que o robô criou — Sigma: sem dado"), (!res.sigma_cadastro_desatualizado && res.sigma_ok && vd.testes_criados != null) ? delta(vd.testes_criados, vd.testes_ontem) : "")}
      ${cartao("i-chat", "#fbbf24", "áudios de teste enviados", int(vd.audio), "", delta(vd.audio, vd.audio_ontem))}
    </div>${rv.por_painel ? `<h4>Renovações por painel</h4>${colunas(Object.entries(rv.por_painel).sort())}` : ""}${previsaoBloco(A, j)}` : (!filtrado && j.periodo === "hoje" ? `<p class="nota">Vendas, testes, renovações e pagamentos: sem dado — o resumo do /contagem ainda não chegou.</p>${previsaoBloco(A, j)}` : "")}`));

    // 7. Problemas
    H.push(blocos("Problemas que os clientes trouxeram", "i-alert", `<div class="bolhas-pb">${A.pb.map(([n, v], i) => { const t = 64 + Math.sqrt(v / Math.max(A.pb[0][1], 1)) * 56; return `<div class="bolha" style="width:${t}px;height:${t}px;border-color:${COR[i % 10]}"><b>${int(v)}</b><span>${e(n)}</span></div>`; }).join("") || `<p class="vazio">nenhum problema neste filtro</p>`}</div>
      <div class="mcs">${cartao("i-alert", "#f87171", "conversas com problema", int(A.pb_conv), `${pct(A.pb_conv, A.rc)}% das conversas`, delta(A.pb_conv, b("pb_conv"), true))}
      ${cartao("i-repeat", "#fb923c", "problema repetido (3+ vezes)", int(A.rep.reduce((a, x) => a + x[1], 0)), A.rep.slice(0, 2).map((x) => e(x[0])).join(" · "), "")}</div>`));

    // 8. Apps
    const totApp = A.atend;
    const comApp = totApp - A.sem_app;
    const topApp = A.apps[0];
    const topTeste = A.testados.find((x) => x[0] !== "App não identificado");
    const totIns = A.ins.reduce((a, x) => a + x[1], 0);
    H.push(blocos("Aplicativos", "i-box", `<p class="frase-met">Dos <b>${int(totApp)}</b> atendidos, <b>${int(comApp)}</b> têm o app identificado na conversa. <b>${int(A.sem_app)}</b> ainda sem app identificado.</p>
      <div class="destaques-app">
        ${topApp ? `<div class="da">${selo(topApp[0])}<div><small>mais usado</small><b>${e(topApp[0])}</b><span>${int(topApp[1])} clientes</span></div></div>` : ""}
        ${topTeste ? `<div class="da">${selo(topTeste[0])}<div><small>mais testado ${j.periodo === "hoje" ? "hoje" : ""}</small><b>${e(topTeste[0])}</b><span>${int(topTeste[1])} testes</span></div></div>` : `<div class="da"><span class="app-logo" style="background:#334155">?</span><div><small>mais testado</small><b>—</b><span>${int(A.ts)} testes sem app dito</span></div></div>`}
        <div class="da"><span class="app-logo" style="background:#0d9488"><svg class="i"><use href="#i-check"/></svg></span><div><small>instalação passada</small><b>${int(totIns)} apps</b><span>${int(A.cr)} clientes receberam login</span></div></div>
      </div>
      <div class="apps-grade">${A.apps.map(([n, v]) => `<div class="app-card">${selo(n)}<b>${e(n)}</b><div class="track"><div class="fill" style="width:${pct(v, topApp ? topApp[1] : 1)}%;background:${(APPS[n] || {}).c || "#64748b"}"></div></div><span><b>${int(v)}</b> clientes · ${pct(v, comApp)}%</span>${(A.ins.find((x) => x[0] === n) || [0, 0])[1] ? `<small>${int(A.ins.find((x) => x[0] === n)[1])} instalações passadas</small>` : ""}</div>`).join("")}</div>
      <p class="nota">Vale a última menção de um app só (cliente, robô ou equipe) nas mensagens do dia e das 24 horas anteriores. Se o app não apareceu nesse trecho, fica "sem app identificado" — não inventamos. "Instalação passada" = mandamos o passo a passo daquele app; "login" = mandamos usuário e senha. Fun Play saiu do ar.</p>`));

    // 9. Aparelhos
    const comDev = totApp - A.sem_dev;
    H.push(blocos("Aparelhos", "i-tv", `<p class="frase-met">Dos <b>${int(totApp)}</b> atendidos, <b>${int(comDev)}</b> disseram o aparelho. <b>${int(A.sem_dev)}</b> sem aparelho identificado.</p>
      <div class="apps-grade">${A.devs.map(([n, v]) => `<div class="app-card">${devIc(n)}<b>${e(n)}</b><div class="track"><div class="fill" style="width:${pct(v, A.devs[0][1])}%;background:${(DEVS[n] || {}).c || "#64748b"}"></div></div><span><b>${int(v)}</b> · ${pct(v, comDev)}%</span></div>`).join("")}</div>`));

    // 10. Fila
    H.push(blocos("Fila de espera", "i-hourglass", graficoFila(regs, j)));

    // 11. Dia a dia
    if (dados["7d"] || j.periodo === "7d") H.push(blocos("Dia a dia", "i-pulse", diaADia((dados["7d"] || j).conversas.filter(passa), res)));
    else H.push(blocos("Dia a dia", "i-pulse", `<button type="button" class="btn-sec" id="btnDias">Ver os últimos dias</button>`));

    // 12. Qualidade do robô (resumo do Telegram)
    if (res && res.qualidade && !filtrado) {
      const q = res.qualidade;
      H.push(blocos("Qualidade do robô (dia inteiro)", "i-bot", `<div class="dupla">
        ${rosca([["Satisfeitos", q.satisfeitos || 0, "#34d399"], ["Reclamaram", q.reclamaram || 0, "#f87171"], ["Outras respostas", Math.max(0, (q.responderam || 0) - (q.satisfeitos || 0) - (q.reclamaram || 0)), "#94a3b8"]], int(q.responderam), "responderam")}
        ${legenda([["Pesquisas enviadas", q.feedback], ["Satisfeitos", q.satisfeitos, "#34d399"], ["Reclamaram", q.reclamaram, "#f87171"]])}</div>
        <div class="mcs">${cartao("i-alert", q.erro_pct > 6 ? "#f87171" : "#34d399", "erros do robô", `${String(q.erro_pct ?? "—").replace(".", ",")}%`, `${int(q.erro_real)} de ${int(q.msgs_env)} mensagens`, "")}
        ${cartao("i-lock", "#fbbf24", "conversas seguradas", int(q.trava_conv), `${int(q.trava_ev)} vezes`, delta(q.trava_conv, q.trava_conv_ontem, true))}</div>
        <h4>Erros mais comuns</h4>${barras((q.erros || []).map((x) => [x.nome, x.n]), "#f87171")}
        <h4>Mensagens seguradas antes de sair</h4>${barras((q.barrados || []).map((x) => [x.nome, x.n]), "#fbbf24")}`));
    }
    $m("#metCorpo").innerHTML = H.join("");
    const bd = $m("#btnDias");
    if (bd) bd.addEventListener("click", async () => { bd.textContent = "Carregando…"; await carregar("7d"); desenhar(j); });
  }
  function previsaoAtend(A, iso) {
    const m = String(iso || "").match(/T(\d{2}):(\d{2})/);
    if (!m) return { sem: "sem dado — ainda não dá para estimar o fim do dia" };
    const h = Number(m[1]);
    const min = Number(m[2]);
    const decorrido = h + min / 60;
    if (decorrido < 1) return { sem: "sem dado — ainda não dá para estimar o fim do dia" };
    const regs = A.regs.filter((r) => r.rc || r.ma);
    const comHora = regs.filter((r) => r.h0 != null);
    if (!comHora.length) {
      return { fecha: Math.round((regs.length / decorrido) * 24), frase: "Estimativa pelo ritmo desde meia-noite. Pode mudar." };
    }
    const ini = Math.max(0, h - 2);
    const janelaH = Math.max(0.5, decorrido - ini);
    const recentes = comHora.filter((r) => r.h0 >= ini && r.h0 <= h).length;
    const fecha = Math.round(regs.length + (recentes / janelaH) * (24 - decorrido));
    return { fecha, frase: "Soma o que já entrou com o ritmo das últimas 3 horas até meia-noite. Pode mudar." };
  }
  function previsaoBloco(A, j) {
    if (j.periodo !== "hoje") return "";
    const p = (typeof estado !== "undefined" && estado && estado.destaques && estado.destaques.previsao) || null;
    const dinheiro = p && p.v != null
      ? cartao("i-pulse", "#34d399", "previsão de fechamento (dinheiro)", brl(p.v), e(p.nota || p.frase || ""), "")
      : cartao("i-pulse", "#94a3b8", "previsão de fechamento (dinheiro)", "—", "sem dado — ainda não dá para estimar o fim do dia", "");
    const at = previsaoAtend(A, j.calculado_em);
    const gente = at.fecha != null
      ? cartao("i-users", "#a78bfa", "previsão de atendidos até meia-noite", int(at.fecha), e(at.frase), "")
      : cartao("i-users", "#94a3b8", "previsão de atendidos até meia-noite", "—", e(at.sem || "sem dado — ainda não dá para estimar o fim do dia"), "");
    return `<h4>Previsão de fechamento do dia</h4><div class="mcs">${dinheiro}${gente}</div>`;
  }
  function colunasHora(h) {
    const max = Math.max(...h, 1);
    return `<div class="colh">${h.map((v, i) => `<i style="height:${Math.max(2, (v / max) * 56)}px" title="${i}h: ${v}"></i>`).join("")}</div><div class="calor-eixo"><span>0h</span><span>6h</span><span>12h</span><span>18h</span><span>23h</span></div>`;
  }
  function colunas(lista) {
    const max = Math.max(...lista.map((x) => x[1]), 1);
    return `<div class="colunas">${lista.map(([n, v], i) => `<div class="col"><b>${int(v)}</b><i style="height:${(v / max) * 70 + 4}px;background:${COR[i % 10]}"></i><span>${e(n)}</span></div>`).join("")}</div>`;
  }
  function faixas(t1) {
    const f = [["até 1 min", 0, 60, "#34d399"], ["1 a 5 min", 60, 300, "#a3e635"], ["5 a 15 min", 300, 900, "#fbbf24"], ["15 a 30 min", 900, 1800, "#fb923c"], ["mais de 30 min", 1800, 1e12, "#f87171"]];
    const n = t1.length || 1;
    return `<div class="faixas">${f.map(([nome, a, b, c]) => { const q = t1.filter((v) => v >= a && v < b).length; return `<div style="flex:${Math.max(q, 0.0001)};background:${c}" title="${nome}: ${q}"></div>`; }).join("")}</div>
      <div class="leg leg-linha">${f.map(([nome, a, b, c]) => { const q = t1.filter((v) => v >= a && v < b).length; return `<div><i style="background:${c}"></i><span>${nome}</span><b>${pct(q, n)}%</b></div>`; }).join("")}</div>`;
  }
  function passe(i1, n1, i2, n2, v, txt) {
    return `<div class="passe"><span class="pi"><svg class="i"><use href="#${i1}"/></svg></span><svg class="i seta"><use href="#i-arrow"/></svg><span class="pi"><svg class="i"><use href="#${i2}"/></svg></span><b class="num">${int(v)}</b><small>${e(txt)}</small></div>`;
  }
  function graficoFila(regs, j) {
    const f = fila(regs);
    if (!f) return `<p class="vazio">ninguém ficou esperando neste período</p>`;
    const ks = Object.keys(f.pontos).map(Number).sort((a, b) => a - b);
    const ini = ks[0], fim = ks[ks.length - 1];
    const W = 600, Hh = 120;
    const max = Math.max(f.max, 1);
    const pts = [];
    let ult = 0;
    for (let k = ini; k <= fim; k += 15) { ult = f.pontos[k] != null ? f.pontos[k] : ult; pts.push([k, f.pontos[k] != null ? f.pontos[k] : 0]); }
    const x = (k) => ((k - ini) / Math.max(fim - ini, 1)) * W;
    const y = (v) => Hh - (v / max) * (Hh - 8);
    const d = pts.map(([k, v], i) => `${i ? "L" : "M"}${x(k).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
    const px = x(Math.floor(f.quando / 15) * 15);
    const quando = j.periodo === "7d" ? new Date(f.quando * 60000).toLocaleString("pt-BR", { weekday: "short", hour: "2-digit", minute: "2-digit", timeZone: "America/Bahia" }) : hhmm(f.quando);
    return `<div class="alerta-fila"><svg class="i"><use href="#i-alert"/></svg><div><b>Pior momento: ${int(f.max)} clientes esperando ao mesmo tempo</b><span>às ${e(quando)}</span></div></div>
      <svg class="fila-svg" viewBox="0 0 ${W} ${Hh + 4}" preserveAspectRatio="none"><path d="${d} L${W},${Hh} L0,${Hh} Z" fill="rgba(251,146,60,.18)"/><path d="${d}" fill="none" stroke="#fb923c" stroke-width="2"/><line x1="${px}" x2="${px}" y1="0" y2="${Hh}" stroke="#f87171" stroke-dasharray="4 4"/><circle cx="${px}" cy="${y(f.max)}" r="5" fill="#f87171"/></svg>
      <div class="calor-eixo"><span>${e(hhmm(ini))}</span><span>${e(hhmm(fim))}</span></div><p class="nota">Quantos clientes estavam esperando resposta ao mesmo tempo, de 15 em 15 minutos. Quem ficou mais de 2 horas sem retorno sai desta conta (já aparece em "sem resposta").</p>`;
  }
  function diaADia(regs, res) {
    const dias = {};
    regs.forEach((r) => (dias[r.d] = dias[r.d] || []).push(r));
    const semana = {};
    ((res && res.semana) || []).forEach((s) => (semana[s.dia] = s));
    const lista = Object.keys(dias).sort().map((d) => { const c = calc(dias[d]); return { d, t1: c.t1_med, sr: pct(c.sr, c.ne), atend: c.atend, erro: (semana[d] || {}).erro_pct, renov: (semana[d] || {}).renovado_ok ? semana[d].renovado_n : null }; });
    const nomeDia = (d) => new Date(d + "T12:00:00-03:00").toLocaleDateString("pt-BR", { weekday: "short", day: "2-digit" });
    const linha = (campo, rot, cor, fmt, menorMelhor, contagem) => {
      const v = lista.map((x) => x[campo]);
      const val = v.filter((z) => z != null);
      if (!val.length) return `<div class="dd"><div class="dd-t">${e(rot)}</div><p class="vazio">sem dado</p></div>`;
      const max = Math.max(...val, 1), W = 300, H = 70;
      const xs = (i) => (lista.length > 1 ? (i / (lista.length - 1)) * (W - 20) + 10 : W / 2);
      const ys = (z) => H - 8 - (z / max) * (H - 20);
      const pts = v.map((z, i) => (z == null ? null : [xs(i), ys(z)])).filter(Boolean);
      const dd = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
      const ult = val[val.length - 1];
      const antes = val.length > 1 ? val.slice(0, -1).reduce((x, y) => x + y, 0) / (val.length - 1) : ult;
      const igual = Math.abs(ult - antes) <= Math.abs(antes) * 0.05;
      const melhorou = menorMelhor ? ult < antes : ult > antes;
      const selo = contagem ? `<span class="dl igual">hoje ainda não acabou</span>` : `<span class="dl ${igual ? "igual" : melhorou ? "bom" : "ruim"}" title="hoje comparado com a média dos dias anteriores">${igual ? "estável" : melhorou ? "melhorando" : "piorando"}</span>`;
      return `<div class="dd"><div class="dd-t">${e(rot)} ${selo}</div>
        <svg viewBox="0 0 ${W} ${H}"><path d="${dd}" fill="none" stroke="${cor}" stroke-width="2.5"/>${pts.map((p, i) => `<circle cx="${p[0]}" cy="${p[1]}" r="3.5" fill="${cor}"/>`).join("")}</svg>
        <div class="dd-x">${lista.map((x) => `<span><b>${x[campo] == null ? "—" : e(fmt(x[campo]))}</b>${e(nomeDia(x.d))}</span>`).join("")}</div></div>`;
    };
    return `<div class="dds">${linha("t1", "1ª resposta (metade em até)", "#22d3ee", tempo, true)}${linha("sr", "Ficaram sem resposta", "#f87171", (z) => z + "%", true)}${linha("erro", "Erros do robô", "#fbbf24", (z) => String(z).replace(".", ",") + "%", true)}${linha("atend", "Clientes atendidos", "#a78bfa", int, false, true)}${linha("renov", "Renovações conferidas", "#34d399", int, false, true)}</div>
      <p class="nota">"Melhorando/piorando" compara hoje com a média dos dias anteriores. O histórico das conversas começou há poucos dias, então os primeiros dias podem estar incompletos.</p>`;
  }

  document.addEventListener("click", (ev) => {
    const b = ev.target.closest("[data-periodo]");
    if (!b) return;
    periodo = b.dataset.periodo;
    document.querySelectorAll("[data-periodo]").forEach((x) => x.classList.toggle("on", x === b));
    $m("#fraseMet").textContent = "Carregando…";
    atualizar(false);
  });
  const liga = (sel, chave) => document.addEventListener("change", (ev) => { if (ev.target.matches(sel)) { filtro[chave] = ev.target.value; atualizar(false); } });
  liga("#fNumero", "n"); liga("#fAtendente", "at"); liga("#fApp", "app"); liga("#fAparelho", "dev");
  document.addEventListener("click", (ev) => { if (ev.target.matches("#fLimpar")) { Object.keys(filtro).forEach((k) => (filtro[k] = "")); atualizar(false); } });
  return { abrir };
})();
