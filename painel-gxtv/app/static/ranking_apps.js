/* APPS1910 (19/10): visual novo da aba Apps (desenhar); o antigo ficou em desenharAntigo.
   RANKING_VISUAL_0810 — aba Ranking apps no padrão dos cards escuros (Ao vivo / Início).
   Dados: /api/ranking-apps-metricas → "fichas" = ranking_fichas.json (arquivo local; zero API DataCrazy).
   Logos: /static/logos/<app>.png (servidas pelo próprio painel). */
(function () {
  const $ = (s, r) => (r || document).querySelector(s);
  const e = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const int = (n) => (Number(n) || 0).toLocaleString("pt-BR");
  const pct = (n, casas) => (n == null || isNaN(n)) ? "—" : (Number(n) * 100).toFixed(casas == null ? 0 : casas).replace(".", ",") + "%";
  const LOGOS = new Set(["brasil", "max", "utra", "xciptv", "mntech", "xp", "flex", "ibo", "downloader", "zuxo", "lotus"]);
  const tom = (t) => t == null ? "rk-t-sem" : t >= 0.6 ? "rk-t-bom" : t >= 0.45 ? "rk-t-medio" : "rk-t-ruim";
  let ocupado = false;

  function logo(app, nome, cls) {
    if (LOGOS.has(app)) return `<img class="${cls}" src="/static/logos/${e(app)}.png?v=1910" alt="${e(nome || app)}" loading="lazy">`;
    const ini = String(nome || app || "?").replace(/[^A-Za-z0-9 ]/g, "").split(" ").filter(Boolean).map((p) => p[0]).join("").slice(0, 2).toUpperCase();
    return `<span class="${cls} rk-logo-letra">${e(ini || "?")}</span>`;
  }
  const deprimeira = (a) => a && a.primeiro ? a.de_primeira / a.primeiro : null;
  const reclPct = (a) => a && a.fichas ? a.reclamou / a.fichas : null;

  function posicao(i, a, key, baixa) {
    const nome = (a && a.nome) || key;
    if (!a) return `<div class="rk-pos"><span class="rk-rank">${i + 1}º</span>${logo(key, nome, "rk-logo")}<div class="rk-app">${e(nome)}</div><p class="rk-nota">sem ficha</p></div>`;
    return `<div class="rk-pos${i === 0 ? " rk-pos1" : ""}">
      <span class="rk-rank">${i + 1}º</span>
      ${logo(key, nome, "rk-logo")}
      <div class="rk-app">${e(nome)}</div>
      <div class="rk-taxa ${tom(a.taxa)} num">${pct(a.taxa)}</div>
      <div class="rk-taxa-rot">taxa de acerto</div>
      <div class="rk-barra"><i class="${tom(a.taxa)}" style="width:${Math.round((a.taxa || 0) * 100)}%"></i></div>
      <div class="rk-mets">
        <div><small>De primeira</small><b class="num">${pct(deprimeira(a))}</b><span>${int(a.de_primeira)}/${int(a.primeiro)}</span></div>
        <div><small>Reclamações</small><b class="num rk-recl">${int(a.reclamou)}</b><span>${pct(reclPct(a))} das fichas</span></div>
        <div><small>Fichas</small><b class="num">${int(a.fichas)}</b><span title="funcionou · falhou">${int(a.resolveu)} ok · ${int(a.falhou)} ✗</span></div>
      </div>
      ${baixa ? `<span class="rk-selo">amostra baixa</span>` : ""}
    </div>`;
  }

  function aparelho(key, b) {
    const apps = b.apps || [];
    const por = {};
    apps.forEach((a) => { por[a.app] = a; });
    const ordem = b.ordem || [];
    const baixa = new Set(b.amostra_baixa || []);
    const robo = b.ordem_robo || [];
    const igual = robo.join(">") === ordem.join(">");
    const outros = apps.filter((a) => !ordem.includes(a.app));
    const linhas = outros.map((a) => `<tr class="${a.proibido ? "rk-ban" : ""}">
        <td>${logo(a.app, a.nome, "rk-logo-mini")}<span>${e(a.nome || a.app)}</span>${a.proibido ? '<em class="rk-tag-ban">banido</em>' : ""}${(b.fora_lista || []).includes(a.app) ? '<em class="rk-tag-ok">bom, fora da lista</em>' : ""}</td>
        <td class="num ${tom(a.taxa)}">${pct(a.taxa)}</td><td class="num">${pct(deprimeira(a))}</td>
        <td class="num">${int(a.reclamou)}</td><td class="num">${int(a.fichas)}</td></tr>`).join("");
    const trocas = (b.trocas || []).slice(0, 3).map((t) => `<span class="rk-troca">${e((por[t.de] || {}).nome || t.de)} → ${e((por[t.para] || {}).nome || t.para)} <b>${int(t.resolveu)}/${int(t.n)}</b></span>`).join("");
    return `<article class="rk-ap">
      <header><b>${e(b.nome || key)}</b><span class="rk-ap-n num">${int(b.fichas)} fichas</span></header>
      <div class="rk-sub">Ordem pelas fichas</div>
      <div class="rk-ordem" style="--cols:${Math.max(3, Math.min(ordem.length, 4))}">${ordem.map((k, i) => posicao(i, por[k], k, baixa.has(k))).join("") || '<p class="rk-nota">sem ordem (amostra pequena)</p>'}</div>
      <div class="rk-robo"><span>Robô usa hoje:</span>${robo.map((k) => logo(k, (por[k] || {}).nome || k, "rk-logo-mini")).join('<i class="rk-seta">›</i>') || "—"}
        <em class="${igual ? "rk-igual" : "rk-dif"}">${igual ? "igual às fichas" : "diferente das fichas"}</em></div>
      ${trocas ? `<div class="rk-trocas"><small>Trocas que mais aconteceram (resolveu/vezes):</small>${trocas}</div>` : ""}
      ${outros.length ? `<details class="rk-outros"><summary>Outros apps vistos nas fichas (${outros.length})</summary>
        <table><thead><tr><th>App</th><th>Acerto</th><th>De 1ª</th><th>Reclam.</th><th>Fichas</th></tr></thead><tbody>${linhas}</tbody></table></details>` : ""}
    </article>`;
  }

  function placar(j) {
    const rows = (j.linhas || []).map((r) => `<tr><td>${e(r.aparelho)}</td><td>${logo(r.app, r.nome, "rk-logo-mini")}<span>${e(r.nome || r.app)}</span></td>
      <td class="num ${tom(r.taxa_4h)}">${pct(r.taxa_4h, 1)}</td><td class="num">${int(r.n_4h)}</td>
      <td class="num ${tom(r.taxa_7d)}">${pct(r.taxa_7d, 1)}</td><td class="num">${int(r.n_7d)}</td></tr>`).join("");
    if (!rows) return "";
    return `<details class="rk-outros rk-placar"><summary>Placar ao vivo (fichas: 4 h e 7 dias)</summary>
      <table><thead><tr><th>Aparelho</th><th>App</th><th>Acerto 4h</th><th>N 4h</th><th>Acerto 7d</th><th>N 7d</th></tr></thead><tbody>${rows}</tbody></table></details>`;
  }

  function desenharAntigo(j) {
    const box = $("#ranking-apps-corpo");
    if (!box) return;
    const fx = j.fichas;
    if (!fx || !fx.aparelhos) { box.innerHTML = `<p class="rk-nota">ranking_fichas.json indisponível agora.</p>${placar(j)}`; return; }
    const aps = Object.entries(fx.aparelhos).sort((a, b) => (b[1].fichas || 0) - (a[1].fichas || 0));
    const g = fx.geral || {};
    const kpi = (rot, val, sub) => `<div class="rk-kpi"><div class="rk-rot">${rot}</div><div class="rk-big num">${val}</div><div class="rk-ksub">${sub || ""}</div></div>`;
    box.innerHTML = `
      <div class="rk-topo"><h2>Ranking de apps por aparelho</h2><button type="button" class="rk-btn" id="rk-atualizar">Atualizar</button></div>
      <div class="rk-kpis">
        ${kpi("Fichas lidas", int(g.lidas), `${int(g.sem_aparelho)} sem aparelho`)}
        ${kpi("Aparelhos", int(aps.length), "com ordem calculada")}
        ${kpi("Atualizado", e(String(fx.gerado_em || "—").slice(11, 16) || "—"), e(String(fx.gerado_em || "").slice(0, 10)))}
        ${kpi("Mínimo pra ordem", int(fx.min_n_ordem), "fichas com resultado")}
      </div>
      <p class="rk-leg"><b>Taxa de acerto</b> = funcionou ÷ (funcionou + falhou). <b>De primeira</b> = funcionou quando foi o 1º app tentado.
        <b>Reclamações</b> = fichas em que o cliente reclamou desse app. <b>Fichas</b> = fichas em que o app apareceu.</p>
      <div class="rk-grade">${aps.map(([k, b]) => aparelho(k, b)).join("")}</div>
      ${placar(j)}
      <p class="rk-nota">Fonte: ranking_fichas.json neste servidor (recalculado a cada 10 min). Só leitura; não muda a ordem do robô. Sem API do DataCrazy.</p>`;
    const btn = $("#rk-atualizar");
    if (btn) btn.addEventListener("click", atualizar);
  }

  /* APPS1910 — visual novo: "Precisa de decisão" + 1 card por aparelho com a ordem das regras do Gustavo.
     Desligar: localStorage.rk_visual="antigo" (só neste navegador) ou RANKING_APPS_VISUAL=antigo no serviço. */
  let jan = "7d";
  let ultimo = null;
  const MIN = 10;
  const cor = (ok, n) => n < MIN ? "ra-cinza" : ok / n >= 0.7 ? "ra-verde" : ok / n >= 0.5 ? "ra-amarelo" : "ra-vermelho";
  const p100 = (ok, n) => n ? Math.round(100 * ok / n) + "%" : "—";
  const NOMES = { zuxo: "Zuxo Player", lotus: "Lótus", utra: "UTRA PLUS", max: "Max Player", brasil: "Brasil IPTV", xciptv: "XCIPTV", mntech: "MN TECH", xp: "XP IPTV", flex: "Flex Play" };
  const nomeDe = (c, k) => NOMES[k] || ((c.apps || {})[k] || {}).nome || k;

  function analisa(c) {
    const apps = c.apps || {};
    const v = (k) => { const a = apps[k] || {}; return { ok: a["ok_" + jan] || 0, n: a["n_" + jan] || 0, a }; };
    let melhor = null;
    (c.ordem || []).forEach((k) => { const x = v(k); if (x.n >= MIN && (!melhor || x.ok / x.n > melhor.t)) melhor = { k, t: x.ok / x.n, ok: x.ok, n: x.n }; });
    const avisos = [];
    const p1 = (c.ordem || [])[0];
    if (melhor && p1 && melhor.k !== p1) {
      const x = v(p1);
      const dif = x.n >= MIN ? melhor.t - x.ok / x.n : 1;
      if (dif >= 0.10) avisos.push({ peso: 100 + dif * 100, txt: `${nomeDe(c, melhor.k)} (${p100(melhor.ok, melhor.n)}, ${melhor.ok} de ${melhor.n}) está melhor que o 1º da ordem, ${nomeDe(c, p1)} (${x.n ? p100(x.ok, x.n) + ", " + x.ok + " de " + x.n : "sem casos"})` });
    }
    (c.proibidos || []).forEach((p) => {
      const n = p.desde ? (p.fichas_desde || 0) : (p["fichas_" + jan] || 0);
      if (!n || (!p.desde && n < 5)) return;  // sem data: só avisa com 5+ fichas (evita ruído de 2-3 casos)
      const quando = p.desde ? `desde ${p.desde}` : (jan === "7d" ? "na semana" : "em 30 dias");
      avisos.push({ peso: (p.desde ? 300 : 0) + n, forte: p.desde || n >= MIN, txt: `${p.nome || nomeDe(c, p.app)} apareceu em ${n} ficha${n > 1 ? "s" : ""} ${quando}${p.desde ? ", quando passou a ser proibido aqui (regra do Gustavo)" : ", mas as regras proíbem aqui"}` });
    });
    return { melhor, avisos, v };
  }

  function linhaApp(c, k, i, v) {
    const x = v(k);
    const aviso = x.n >= MIN ? "" : x.n ? '<em>poucos casos</em>' : '<em>sem ficha no período</em>';
    const hist = x.a.hist_n ? `${p100(x.a.hist_ok, x.a.hist_n)} de ${int(x.a.hist_n)}` : "sem histórico";
    return `<tr${i === 0 ? ' class="ra-1o"' : ""}><td class="ra-pos">${i + 1}º</td>
      <td class="ra-app">${logo(k, nomeDe(c, k), "ra-logo")}<span>${e(nomeDe(c, k))}</span></td>
      <td class="ra-pct num ${cor(x.ok, x.n)}">${p100(x.ok, x.n)}</td>
      <td class="ra-xy num">${int(x.ok)} de ${int(x.n)}${aviso}</td>
      <td class="ra-hist num">${hist}</td></tr>`;
  }

  function card(c, an) {
    const m = an.melhor;
    const nf = c["fichas_" + jan] || 0;
    const best = m ? `<div class="ra-best"><small>Melhor agora</small>${logo(m.k, nomeDe(c, m.k), "ra-logo")}<b>${e(nomeDe(c, m.k))}</b><span class="num ${cor(m.ok, m.n)}">${p100(m.ok, m.n)}</span><small class="num">(${m.ok} de ${m.n})</small></div>`
      : `<div class="ra-best ra-cinza">Ainda sem casos suficientes no período</div>`;
    const avisos = an.avisos.map((a) => `<p class="ra-warn">⚠ ${e(a.txt)}.</p>`).join("");
    return `<article class="ra-card">
      <header><b>${e(c.nome)}</b><span class="num">${int(nf)} fichas ${jan === "7d" ? "na semana" : "em 30 dias"}</span></header>
      ${best}
      <table class="ra-tab"><thead><tr><th></th><th>Ordem do robô (regras)</th><th>Funcionou</th><th>Casos</th><th class="ra-hist">Histórico</th></tr></thead>
      <tbody>${(c.ordem || []).map((k, i) => linhaApp(c, k, i, an.v)).join("") || '<tr><td colspan="5" class="ra-cinza">ordem não encontrada nas regras</td></tr>'}</tbody></table>
      ${avisos}
    </article>`;
  }

  function detalhes(j, fx, cards) {
    const g = fx.geral || {};
    const outros = cards.map((c) => {
      const lst = Object.entries(c.apps || {}).filter(([k, a]) => !(c.ordem || []).includes(k) && (a["visto_" + jan] || 0) > 0)
        .sort((a, b) => (b[1]["visto_" + jan] || 0) - (a[1]["visto_" + jan] || 0)).slice(0, 8)
        .map(([k, a]) => `${e(a.nome || k)}${a.proibido ? " (banido)" : a.terceiro ? " (terceiro)" : ""} <b class="num">${int(a["visto_" + jan])}</b>`).join(" · ");
      return lst ? `<li><b>${e(c.nome)}:</b> ${lst}</li>` : "";
    }).join("");
    return `<details class="rk-outros ra-det"><summary>Detalhes (números gerais, outros apps, placar 4 h, visual antigo)</summary>
      <p class="rk-nota">Fichas lidas: <b>${int(g.lidas)}</b> (${int(g.com_app)} com app) · sem aparelho: ${int(g.sem_aparelho)} · com vários aparelhos: ${int(g.varios_aparelhos)} · apps sem aparelho claro (não contados): ${int(g.app_sem_aparelho_claro)}</p>
      <p class="rk-nota">Ordem lida de ${e((fx.regras_fonte || {}).arquivo || "regras_0810.md")} (alterado ${e((fx.regras_fonte || {}).mtime || "—")}).</p>
      ${outros ? `<p class="rk-nota">Outros apps que apareceram nas fichas (fora da ordem; fichas no período):</p><ul class="ra-outros">${outros}</ul>` : ""}
      ${placar(j)}
      <p><button type="button" class="rk-btn" id="ra-antigo">Ver visual antigo</button></p>
    </details>`;
  }

  function desenhar(j) {
    ultimo = j;
    const fx = j.fichas;
    let antigo = false;
    try { antigo = localStorage.getItem("rk_visual") === "antigo"; } catch (_) {}
    if (!fx || !Array.isArray(fx.cards) || !fx.cards.length || fx.visual === "antigo" || antigo) {
      desenharAntigo(j);
      const t = $(".rk-topo");
      if (t && antigo) t.insertAdjacentHTML("beforeend", '<button type="button" class="rk-btn" id="ra-novo">Visual novo</button>');
      const b = $("#ra-novo");
      if (b) b.addEventListener("click", () => { try { localStorage.removeItem("rk_visual"); } catch (_) {} desenhar(ultimo); });
      return;
    }
    const box = $("#ranking-apps-corpo");
    if (!box) return;
    const cards = fx.cards;
    const ans = cards.map((c) => analisa(c));
    const todos = [];
    cards.forEach((c, i) => ans[i].avisos.forEach((a) => { if (a.peso >= 100 || a.forte) todos.push({ peso: a.peso, txt: `${c.nome}: ${a.txt}` }); }));
    todos.sort((a, b) => b.peso - a.peso);
    const top = todos.slice(0, 3);
    const ger = String(fx.gerado_em || "");
    const hora = ger.slice(11, 16), dia = ger.slice(8, 10) + "/" + ger.slice(5, 7);
    box.innerHTML = `
      <div class="ra-topo"><div><h2>Qual app funciona em cada aparelho</h2>
        <div class="ra-sub">${jan === "7d" ? "Últimos 7 dias" : "Últimos 30 dias"}, pelas fichas · atualizado <b>${e(hora)}</b> de ${e(dia)} · cinza = menos de ${MIN} casos (não decide)</div></div>
        <div class="ra-bts"><button type="button" class="rk-btn${jan === "7d" ? " ra-on" : ""}" data-jan="7d">7 dias</button><button type="button" class="rk-btn${jan === "30d" ? " ra-on" : ""}" data-jan="30d">30 dias</button><button type="button" class="rk-btn" id="rk-atualizar">Atualizar</button></div></div>
      ${top.length ? `<div class="ra-alert"><b>Precisa de decisão</b><ul>${top.map((a) => `<li>${e(a.txt)}</li>`).join("")}</ul>${todos.length > 3 ? `<small>+${todos.length - 3} outro${todos.length - 3 > 1 ? "s" : ""} aviso${todos.length - 3 > 1 ? "s" : ""} dentro dos cards</small>` : ""}</div>` : `<div class="ra-alert ra-ok"><b>Nada pra decidir agora</b> · a ordem das regras bate com as fichas do período.</div>`}
      <div class="ra-grade">${cards.map((c, i) => card(c, ans[i])).join("")}</div>
      <p class="rk-nota">"Funcionou" = fichas em que o app funcionou ÷ fichas com resultado (funcionou ou falhou) no período; cada ficha conta 1 vez por app e por aparelho. Histórico = desde o início das fichas. Só leitura: não muda a ordem do robô.</p>
      ${detalhes(j, fx, cards)}`;
    box.querySelectorAll("[data-jan]").forEach((b) => b.addEventListener("click", () => { jan = b.getAttribute("data-jan"); desenhar(ultimo); }));
    const btn = $("#rk-atualizar");
    if (btn) btn.addEventListener("click", atualizar);
    const ba = $("#ra-antigo");
    if (ba) ba.addEventListener("click", () => { try { localStorage.setItem("rk_visual", "antigo"); } catch (_) {} desenhar(ultimo); });
  }

  async function atualizar() {
    if (ocupado) return;
    ocupado = true;
    const box = $("#ranking-apps-corpo");
    try {
      const r = await fetch("/api/ranking-apps-metricas?periodo=7d", { cache: "no-store" });
      if (!r.ok) throw new Error("HTTP " + r.status);
      desenhar(await r.json());
    } catch (err) {
      if (box) box.innerHTML = `<p class="rk-nota">Não consegui ler o ranking: ${e(err.message || err)}</p>`;
    } finally { ocupado = false; }
  }

  window.RankingAppsMetricas = { atualizar, ligar: function () {} };
})();
