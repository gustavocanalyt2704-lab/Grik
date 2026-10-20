/* SEMANA_1110 — aba "Semana": mensagens por dia da semana, semana atual x anterior.
   Dados: /api/mensagens-semana (queue.jsonl + fluxo_envio_outbox.jsonl; zero API DataCrazy).
   O filtro de instância recalcula no navegador com as contagens por dia×instância. */
(function () {
  const $ = (s, r) => (r || document).querySelector(s);
  const e = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const int = (n) => (Number(n) || 0).toLocaleString("pt-BR");
  const COR = { atual: "#22d3ee", anterior: "#a78bfa" };
  let J = null, sel = null, modo = "total", ocupado = false;
  try { const s = JSON.parse(localStorage.getItem("semana_sel") || "null"); if (Array.isArray(s)) sel = new Set(s); } catch (x) { /* */ }
  try { modo = localStorage.getItem("semana_modo") || "total"; } catch (x) { /* */ }

  const ddmm = (iso) => iso.slice(8, 10) + "/" + iso.slice(5, 7);
  function insts() { return (J.instancias || []).filter((i) => !sel || sel.has(i)); }
  function valor(dia) {
    let r = 0, s = 0;
    insts().forEach((i) => { const v = (J.dados[i] || {})[dia]; if (v) { r += v[0]; s += v[1]; } });
    return modo === "rec" ? r : modo === "env" ? s : r + s;
  }
  // situação do dia: futuro | sem (antes do registro existir) | parcial | ok
  function situacao(dia) {
    if (dia > J.hoje) return "futuro";
    const c = J.cobertura || {};
    const lim = modo === "rec" ? [c.recebidas_desde] : modo === "env" ? [c.enviadas_desde] : [c.recebidas_desde, c.enviadas_desde];
    if (lim.some((d) => !d) || lim.every((d) => dia < d)) return "sem";
    if (lim.some((d) => dia < d) || lim.some((d) => dia === d)) return "parcial";
    if (dia === J.hoje) return "hoje";
    return "ok";
  }

  function grafico() {
    const A = J.datas.atual, B = J.datas.anterior;
    const va = A.map(valor), vb = B.map(valor);
    const sa = A.map(situacao), sb = B.map(situacao);
    const max = Math.max(1, ...va.filter((_, i) => sa[i] !== "futuro" && sa[i] !== "sem"), ...vb.filter((_, i) => sb[i] !== "sem"));
    const W = 760, H = 300, L = 46, R = 10, T = 22, Bm = 48, cw = (W - L - R) / 7, bw = Math.min(34, cw * 0.32);
    const y = (v) => T + (H - T - Bm) * (1 - v / max);
    let g = "";
    for (let k = 0; k <= 4; k++) {
      const v = max * k / 4, yy = y(v);
      g += `<line x1="${L}" x2="${W - R}" y1="${yy}" y2="${yy}" stroke="#1c1c1c"/><text x="${L - 6}" y="${yy + 4}" fill="#7a7a7a" font-size="11" text-anchor="end">${int(Math.round(v))}</text>`;
    }
    const barra = (x, v, st, cor) => {
      if (st === "futuro") return `<text x="${x + bw / 2}" y="${H - Bm - 4}" fill="#4a4a4a" font-size="10" text-anchor="middle">—</text>`;
      if (st === "sem") return `<rect x="${x}" y="${T}" width="${bw}" height="${H - T - Bm}" fill="url(#smHach)" rx="3"/><text x="${x + bw / 2}" y="${H - Bm - 6}" fill="#7a7a7a" font-size="9.5" text-anchor="middle" transform="rotate(-90 ${x + bw / 2} ${H - Bm - 6})" dx="34">sem registro</text>`;
      const yy = y(v), op = st === "parcial" || st === "hoje" ? 0.55 : 1;
      return `<rect x="${x}" y="${yy}" width="${bw}" height="${H - Bm - yy}" fill="${cor}" fill-opacity="${op}" rx="3"><title>${int(v)}${st === "parcial" ? " (dia parcial)" : st === "hoje" ? " (até agora)" : ""}</title></rect>
        <text x="${x + bw / 2}" y="${yy - 4}" fill="#d6d6d6" font-size="10.5" text-anchor="middle">${int(v)}${st === "parcial" ? "*" : ""}</text>`;
    };
    for (let i = 0; i < 7; i++) {
      const cx = L + cw * i + cw / 2;
      g += barra(cx - bw - 2, vb[i], sb[i], COR.anterior) + barra(cx + 2, va[i], sa[i], COR.atual);
      g += `<text x="${cx}" y="${H - Bm + 17}" fill="#f2f2f2" font-size="12.5" font-weight="700" text-anchor="middle">${J.dias[i]}</text>
            <text x="${cx}" y="${H - Bm + 32}" fill="#7a7a7a" font-size="10" text-anchor="middle">${ddmm(B[i])} · ${ddmm(A[i])}</text>`;
    }
    return { svg: `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Mensagens por dia da semana"><defs><pattern id="smHach" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="6" height="6" fill="#0e0e0e"/><line x1="0" y1="0" x2="0" y2="6" stroke="#2a2a2a" stroke-width="3"/></pattern></defs>${g}</svg>`, va, vb, sa, sb };
  }

  function desenhar() {
    const box = $("#semana-corpo");
    if (!box || !J) return;
    const todas = J.instancias || [];
    if (sel) { sel = new Set([...sel].filter((i) => todas.includes(i))); if (!sel.size) sel = null; }
    const G = grafico();
    // comparação justa: só dias que existem nas duas semanas com dado completo (até ontem, + hoje vs mesmo dia)
    let ta = 0, tb = 0, nd = 0;
    for (let i = 0; i < 7; i++) {
      const okA = G.sa[i] !== "futuro" && G.sa[i] !== "sem", okB = G.sb[i] === "ok";
      if (okA && okB) { ta += G.va[i]; tb += G.vb[i]; nd++; }
    }
    const somaA = G.va.reduce((a, v, i) => a + (G.sa[i] === "futuro" || G.sa[i] === "sem" ? 0 : v), 0);
    const somaB = G.vb.reduce((a, v, i) => a + (G.sb[i] === "sem" ? 0 : v), 0);
    const dif = tb ? (ta - tb) / tb : null;
    const semAnt = G.sb.filter((s) => s === "sem").length;
    const c = J.cobertura || {};
    const nomeModo = { total: "total (recebidas + enviadas)", rec: "recebidas (clientes)", env: "enviadas (robô)" }[modo];
    box.innerHTML = `
      <div class="sm-topo"><h2>Mensagens por dia da semana · esta semana × semana passada</h2>
        <div class="sm-ctl">
          <div class="sm-seg" role="group" aria-label="Tipo">
            <button type="button" data-modo="total" class="${modo === "total" ? "on" : ""}">Total</button>
            <button type="button" data-modo="rec" class="${modo === "rec" ? "on" : ""}">Recebidas</button>
            <button type="button" data-modo="env" class="${modo === "env" ? "on" : ""}">Enviadas</button>
          </div>
          <button type="button" class="sm-btn" id="sm-atualizar">Atualizar</button>
        </div></div>
      <div class="sm-card sm-inst"><span class="sm-rot">Instâncias</span>
        <button type="button" class="sm-tag todas ${sel ? "" : "on"}" data-inst="">Todas (${todas.length})</button>
        ${todas.map((i) => `<button type="button" class="sm-tag ${sel && sel.has(i) ? "on" : ""}" data-inst="${e(i)}">${e(i)}</button>`).join("")}
      </div>
      <div class="sm-kpis">
        <div class="sm-card sm-kpi"><div class="r">Esta semana</div><div class="v num" style="color:${COR.atual}">${int(somaA)}</div><div class="s">${ddmm(J.datas.atual[0])} a hoje · ${e(nomeModo)}</div></div>
        <div class="sm-card sm-kpi"><div class="r">Semana passada</div><div class="v num" style="color:${COR.anterior}">${int(somaB)}</div><div class="s">${ddmm(J.datas.anterior[0])} a ${ddmm(J.datas.anterior[6])}${semAnt ? ` · ${semAnt} dia(s) sem registro` : ""}</div></div>
        <div class="sm-card sm-kpi"><div class="r">Variação (dias comparáveis)</div><div class="v num ${dif == null ? "" : dif >= 0 ? "sm-up" : "sm-down"}">${dif == null ? "—" : (dif >= 0 ? "+" : "") + (dif * 100).toFixed(0) + "%"}</div><div class="s">${nd ? `${nd} dia(s) com registro completo nas duas semanas` : "nenhum dia com registro completo nas duas semanas ainda"}</div></div>
      </div>
      ${semAnt ? `<div class="sm-aviso">A semana passada está incompleta: o registro de recebidas começa em ${e((c.recebidas_primeiro || "—").replace("T", " "))} e o de enviadas em ${e((c.enviadas_primeiro || "—").replace("T", " "))}. Dias antes disso aparecem como “sem registro” (não é zero).</div>` : ""}
      <div class="sm-card">
        <div class="sm-leg"><span><i style="background:${COR.anterior}"></i>Semana passada</span><span><i style="background:${COR.atual}"></i>Esta semana</span><span class="sm-nota">barra clara / * = dia parcial ou hoje até agora</span></div>
        <div class="sm-graf">${G.svg}</div>
        <table class="sm-tab"><thead><tr><th>Dia</th>${J.dias.map((d) => `<th>${d}</th>`).join("")}<th>Soma</th></tr></thead><tbody>
          <tr><td style="color:${COR.anterior}">Semana passada</td>${G.vb.map((v, i) => `<td class="num">${G.sb[i] === "sem" ? "—" : int(v) + (G.sb[i] === "parcial" ? "*" : "")}</td>`).join("")}<td class="num"><b>${int(somaB)}</b></td></tr>
          <tr><td style="color:${COR.atual}">Esta semana</td>${G.va.map((v, i) => `<td class="num">${G.sa[i] === "futuro" || G.sa[i] === "sem" ? "—" : int(v) + (G.sa[i] === "parcial" || G.sa[i] === "hoje" ? "*" : "")}</td>`).join("")}<td class="num"><b>${int(somaA)}</b></td></tr>
        </tbody></table>
      </div>
      <p class="sm-nota">Fonte: recebidas = registro do webhook do DataCrazy (queue.jsonl, 1 linha por mensagem do cliente); enviadas = fluxo_envio_outbox.jsonl (mensagens do robô que saíram). Mensagem digitada por humano no DataCrazy não aparece nesses registros. Instância com o mesmo nome do Ao vivo. Horário America/Bahia; semana começa na segunda. Só leitura, sem API do DataCrazy.</p>`;
    box.querySelectorAll("[data-modo]").forEach((b) => b.addEventListener("click", () => { modo = b.dataset.modo; try { localStorage.setItem("semana_modo", modo); } catch (x) { /* */ } desenhar(); }));
    box.querySelectorAll("[data-inst]").forEach((b) => b.addEventListener("click", () => {
      const i = b.dataset.inst;
      if (!i) sel = null;
      else { if (!sel) sel = new Set(); sel.has(i) ? sel.delete(i) : sel.add(i); if (!sel.size || sel.size === todas.length) sel = null; }
      try { localStorage.setItem("semana_sel", JSON.stringify(sel ? [...sel] : null)); } catch (x) { /* */ }
      desenhar();
    }));
    const bt = $("#sm-atualizar"); if (bt) bt.addEventListener("click", atualizar);
  }

  async function atualizar() {
    if (ocupado) return;
    ocupado = true;
    const box = $("#semana-corpo");
    try {
      const r = await fetch("/api/mensagens-semana", { cache: "no-store" });
      if (!r.ok) throw new Error("HTTP " + r.status);
      J = await r.json();
      desenhar();
    } catch (err) {
      if (box) box.innerHTML = `<p class="sm-nota">Não consegui ler as mensagens da semana: ${e(err.message || err)}</p>`;
    } finally { ocupado = false; }
  }
  window.SemanaMensagens = { atualizar };
})();
