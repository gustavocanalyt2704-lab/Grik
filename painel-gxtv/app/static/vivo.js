/* AO_VIVO_WEBHOOK_0810 — aba "Ao vivo": lê /api/vivo (registro do webhook no disco; zero API DataCrazy).
   Pergunta 1x por segundo, só com a aba aberta e a janela visível. */
(function () {
  const $ = (s, r) => (r || document).querySelector(s);
  const esc = (s) => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const int = (n) => (Number(n) || 0).toLocaleString("pt-BR");
  const dec = (n, c) => (Number(n) || 0).toLocaleString("pt-BR", { minimumFractionDigits: c, maximumFractionDigits: c });
  const ha = (s) => {
    if (s == null) return "—";
    if (s < 60) return s + " s";
    if (s < 3600) return Math.floor(s / 60) + " min";
    return Math.floor(s / 3600) + " h " + String(Math.floor((s % 3600) / 60)).padStart(2, "0");
  };
  const TIPOS = [["texto", "Texto"], ["foto", "Foto"], ["audio", "Áudio"], ["video", "Vídeo"], ["arquivo", "Arquivo"], ["outro", "Outro"]];
  let ligado = false, timer = null, emVoo = false, falhas = 0, ultimo = null;

  function setNum(el, txt, semFlash) {
    if (!el) return;
    if (el.textContent !== txt) {
      el.textContent = txt;
      if (semFlash) return;
      el.classList.remove("vv-flash"); void el.offsetWidth; el.classList.add("vv-flash");
    }
  }

  function esqueleto() {
    const box = $("#vivo-corpo");
    if (!box || box.dataset.pronto) return;
    box.dataset.pronto = "1";
    const kpi = (id, rot, sub) => `<div class="vv-kpi"><div class="vv-rot">${rot}</div><div class="vv-big num" id="${id}">—</div><div class="vv-sub" id="${id}Sub">${sub || ""}</div></div>`;
    box.innerHTML = `
      <div class="vv-fonte" id="vvFonte">Lendo o registro do webhook…</div>
      <div class="vv-kpis">
        ${kpi("vvMsgS", "Mensagens / seg", "média do último minuto")}
        ${kpi("vvMsgMin", "Mensagens / min", "média dos últimos 15 min")}
        ${kpi("vvRecS", "Webhooks recebidos / seg", "cliente → robô (último minuto)")}
        ${kpi("vvEnvS", "Webhooks enviados / seg", "robô → cliente (último minuto)")}
        ${kpi("vvRecHoje", "Recebidos hoje", "")}
        ${kpi("vvEnvHoje", "Enviados hoje", "")}
      </div>
      <div class="vv-graf">
        <div class="vv-graf-head"><h3>Segundo a segundo (últimos 2 min)</h3>
          <span class="vv-leg"><i class="vv-c-r"></i>recebido <i class="vv-c-e"></i>enviado</span></div>
        <div class="vv-barras" id="vvBarras"></div>
      </div>
      <div class="vv-graf">
        <div class="vv-graf-head"><h3>Minuto a minuto (última hora)</h3><span class="vv-sub" id="vvMinTxt"></span></div>
        <div class="vv-barras vv-barras-min" id="vvMinutos"></div>
      </div>
      <h3 class="vv-tit">Por número de WhatsApp</h3>
      <div class="vv-nums" id="vvNums"></div>`;
  }

  function barras(host, serie, alturaMax) {
    if (!host) return;
    const max = Math.max(1, ...serie.map((p) => p[0] + p[1]));
    if (host.children.length !== serie.length) {
      host.innerHTML = serie.map(() => `<div class="vv-b"><span class="vv-be"></span><span class="vv-br"></span></div>`).join("");
    }
    serie.forEach((p, i) => {
      const col = host.children[i];
      col.title = `${p[0]} recebido · ${p[1]} enviado`;
      col.children[0].style.height = (p[1] / max) * alturaMax + "px";
      col.children[1].style.height = (p[0] / max) * alturaMax + "px";
    });
  }

  // INICIO_0810: quem atendeu (conversas de hoje), só as 3 primeiras pessoas para não poluir
  function quemLinha(num) {
    // QUEM_WEBHOOK_0810: vem do próprio registro do webhook, em CLIENTES
    const n = ((ultimo || {}).numeros || []).find((x) => x.numero === num) || {};
    const q = (n.robo_clientes ? [["Robô", n.robo_clientes]] : []).concat(n.atribuido || []);
    if (!q.length || !window.quemAtendeuHtml) return "";
    return `<span class="ix-mudo">${(Number(n.clientes_hoje) || 0).toLocaleString("pt-BR")} clientes escreveram · quem atendeu:</span>` + window.quemAtendeuHtml(q, 3);
  }
  function cardNumero(n) {
    const rt = n.rec_tipos || {};
    const totRec = Object.values(rt).reduce((a, b) => a + b, 0) || 1;
    const fatias = TIPOS.filter(([k]) => rt[k]).map(([k, nome]) =>
      `<span class="vv-t vv-t-${k}" style="width:${(rt[k] / totRec) * 100}%" title="${nome}: ${int(rt[k])}"></span>`).join("");
    const legenda = TIPOS.filter(([k]) => rt[k]).map(([k, nome]) => `<span><i class="vv-t-${k}"></i>${nome} ${int(rt[k])}</span>`).join("");
    const et = n.env_tipos || {};
    const envTxt = TIPOS.filter(([k]) => et[k]).map(([k, nome]) => `${nome} ${int(et[k])}`).join(" · ") || "—";
    const recente = Math.min(n.ult_rec_ha_s == null ? 1e9 : n.ult_rec_ha_s, n.ult_env_ha_s == null ? 1e9 : n.ult_env_ha_s);
    const estado = recente < 300 ? "on" : recente < 1800 ? "morno" : "parado";
    const estadoTxt = estado === "on" ? "ATIVO" : estado === "morno" ? "CALMO" : "PARADO";
    return `<article class="vv-num" data-num="${esc(n.numero)}">
      <header><span class="vv-dot vv-${estado}"></span><b>${esc(n.numero)}</b><span class="vv-est vv-${estado}">${estadoTxt}</span></header>
      <div class="vv-grade">
        <div><small>Msgs recebidas hoje</small><b class="num" data-k="rec_hoje">${int(n.rec_hoje)}</b></div>
        <div><small>Msgs do robô hoje</small><b class="num" data-k="env_hoje">${int(n.env_hoje)}</b></div>
        <div><small>Receb./min (15 min)</small><b class="num" data-k="rec_min">${dec(n.rec_min_15, 1)}</b></div>
        <div><small>Env./min (15 min)</small><b class="num" data-k="env_min">${dec(n.env_min_15, 1)}</b></div>
        <div><small>Receb./seg (1 min)</small><b class="num" data-k="rec_s">${dec(n.rec_s_60, 2)}</b></div>
        <div><small>Env./seg (1 min)</small><b class="num" data-k="env_s">${dec(n.env_s_60, 2)}</b></div>
      </div>
      <div class="vv-tipos" title="Tipo do que o cliente mandou hoje">${fatias}</div>
      <div class="vv-leg2">${legenda || "<span>sem recebido hoje</span>"}</div>
      <div class="vv-rodape"><span>Enviado: ${envTxt}</span>${n.nao_saiu_hoje ? `<span class="vv-ruim">não saiu: ${int(n.nao_saiu_hoje)}</span>` : ""}</div>
      <div class="vv-rodape"><span>última recebida há <b data-k="ult_rec">${ha(n.ult_rec_ha_s)}</b></span><span>último envio há <b data-k="ult_env">${ha(n.ult_env_ha_s)}</b></span></div>
      <div class="vv-quem">${quemLinha(n.numero)}</div>
      <div class="vv-agora"><span>últimos 10 s:</span><b data-k="r10">${n.rec_10s}</b> receb. · <b data-k="e10">${n.env_10s}</b> env.</div>
    </article>`;
  }

  function desenhar(j) {
    esqueleto();
    const g = j.geral || {};
    const f = j.fonte || {};
    const erro = [f.erro_recebido && "recebido: " + f.erro_recebido, f.erro_enviado && "enviado: " + f.erro_enviado].filter(Boolean).join(" · ");
    $("#vvFonte").innerHTML = `<span class="vv-dot vv-on"></span> Fonte: <b>registro do webhook</b> neste servidor (recebido = queue.jsonl · enviado = fluxo_envio_outbox.jsonl) · API do DataCrazy: <b>não usada</b> · ${esc((j.hora || "").slice(11, 19))} BRT${erro ? ` · <span class="vv-ruim">${esc(erro)}</span>` : ""}`;
    setNum($("#vvMsgS"), dec(g.msg_s_60, 2));
    $("#vvMsgSSub").textContent = `último seg: ${g.msg_s_1} · últimos 10 s: ${dec(g.msg_s_10, 1)}/s · pico 1 min: ${g.pico_s_60}/s`;
    setNum($("#vvMsgMin"), dec(g.msg_min_15, 1));
    $("#vvMsgMinSub").textContent = `média 15 min · hoje: ${dec(g.msg_min_hoje, 1)}/min`;
    setNum($("#vvRecS"), dec(g.rec_s_60, 2));
    $("#vvRecSSub").textContent = `último seg: ${g.rec_s_1} · ${dec(g.rec_min_15, 1)}/min (15 min)`;
    setNum($("#vvEnvS"), dec(g.env_s_60, 2));
    $("#vvEnvSSub").textContent = `último seg: ${g.env_s_1} · ${dec(g.env_min_15, 1)}/min (15 min)`;
    setNum($("#vvRecHoje"), int(g.rec_hoje));
    $("#vvRecHojeSub").textContent = "mensagens de cliente que chegaram";
    setNum($("#vvEnvHoje"), int(g.env_hoje));
    $("#vvEnvHojeSub").textContent = g.nao_saiu_hoje ? `não saíram: ${int(g.nao_saiu_hoje)}` : "respostas que saíram pelo webhook";
    barras($("#vvBarras"), j.serie_120s || [], 90);
    barras($("#vvMinutos"), j.serie_60min || [], 70);
    const sm = (j.serie_60min || []).reduce((a, p) => a + p[0] + p[1], 0);
    $("#vvMinTxt").textContent = `${int(sm)} mensagens na última hora`;
    const host = $("#vvNums");
    const nums = j.numeros || [];
    const chave = nums.map((n) => n.numero).join("|");
    if (host.dataset.chave !== chave) {
      host.dataset.chave = chave;
      host.innerHTML = nums.map(cardNumero).join("");
    } else {
      nums.forEach((n, i) => {
        const c = host.children[i];
        const novo = document.createElement("div");
        novo.innerHTML = cardNumero(n);
        const nc = novo.firstElementChild;
        c.querySelectorAll("[data-k]").forEach((el) => setNum(el, nc.querySelector(`[data-k="${el.dataset.k}"]`).textContent, el.dataset.k.startsWith("ult")));
        ["header", ".vv-tipos", ".vv-leg2", ".vv-quem"].forEach((s) => { const a = c.querySelector(s), b = nc.querySelector(s); if (a.innerHTML !== b.innerHTML) a.innerHTML = b.innerHTML; });
        const ra = c.querySelectorAll(".vv-rodape")[0], rb = nc.querySelectorAll(".vv-rodape")[0];
        if (ra.innerHTML !== rb.innerHTML) ra.innerHTML = rb.innerHTML;
      });
    }
  }

  async function tique() {
    if (!ligado || emVoo || document.hidden) return;
    emVoo = true;
    try {
      const r = await fetch("/api/vivo", { cache: "no-store" });
      if (r.status === 401) { location.reload(); return; }
      if (!r.ok) throw new Error("HTTP " + r.status);
      ultimo = await r.json();
      falhas = 0;
      desenhar(ultimo);
      $("#vivo-corpo").classList.remove("vv-velho");
    } catch (e) {
      falhas += 1;
      if (falhas >= 3) {
        const box = $("#vivo-corpo");
        if (box) box.classList.add("vv-velho");
        const fonte = $("#vvFonte");
        if (fonte) fonte.textContent = "Sem resposta do servidor. Tentando de novo a cada segundo…";
      }
    } finally {
      emVoo = false;
    }
  }

  function abrir() {
    esqueleto();
    if (ligado) return;
    ligado = true;
    tique();
    timer = setInterval(tique, 1000);
  }
  function fechar() {
    ligado = false;
    if (timer) clearInterval(timer);
    timer = null;
  }
  window.Vivo = { abrir, fechar };
})();
