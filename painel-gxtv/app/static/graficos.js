/* Gráficos ao vivo. Lê /api/graficos (dados que o painel já apura) e o ritmo do stream. */
(function () {
  const $ = (s) => document.querySelector(s);
  let ultimo = null;
  let envioAoVivo = [];
  let timer = null;

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  function brl(v) {
    if (v == null || Number.isNaN(Number(v))) return "sem dado";
    return "R$ " + Math.round(Number(v)).toLocaleString("pt-BR");
  }
  function num(v) {
    if (v == null || Number.isNaN(Number(v))) return "sem dado";
    return Number(v).toLocaleString("pt-BR");
  }

  function cartao(titulo, sub, miolo) {
    return `<article class="gx-card"><header><h3>${esc(titulo)}</h3><p>${esc(sub || "")}</p></header>${miolo}</article>`;
  }
  function vazio(motivo) {
    return `<p class="gx-vazio">${esc(motivo || "sem dado")}</p>`;
  }

  function linha(hostW, series, rotulos, opts) {
    opts = opts || {};
    const w = 640, h = opts.h || 168;
    const L = 36, R = 10, T = 14, B = 22;
    const todos = series.flatMap((s) => s.dados.filter((v) => v != null).map(Number));
    if (!todos.length) return vazio(opts.motivo);
    const max = Math.max(opts.max || 0, ...todos, 1);
    const n = Math.max(...series.map((s) => s.dados.length), 1);
    const x = (i) => L + ((w - L - R) * i) / Math.max(1, n - 1);
    const y = (v) => T + (h - T - B) * (1 - v / max);
    let g = "";
    for (let k = 0; k <= 3; k++) {
      const v = (max * k) / 3;
      const yy = y(v);
      g += `<line x1="${L}" x2="${w - R}" y1="${yy}" y2="${yy}" stroke="rgba(255,255,255,.08)"/>`;
      g += `<text x="${L - 6}" y="${yy + 3}" fill="#8b93a7" font-size="10" text-anchor="end">${esc(opts.eixo ? opts.eixo(v) : Math.round(v))}</text>`;
    }
    if (opts.marca != null) {
      const yy = y(opts.marca);
      g += `<line x1="${L}" x2="${w - R}" y1="${yy}" y2="${yy}" stroke="#f87171" stroke-dasharray="4 4"/>`;
      g += `<text x="${w - R}" y="${yy - 4}" fill="#f87171" font-size="10" text-anchor="end">teto ${esc(opts.marca)}</text>`;
    }
    series.forEach((s) => {
      const pts = s.dados.map((v, i) => (v == null ? null : [x(i), y(Number(v))])).filter(Boolean);
      if (pts.length < 2) return;
      const d = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
      if (s.area) {
        const base = `L${pts[pts.length - 1][0].toFixed(1)} ${y(0)} L${pts[0][0].toFixed(1)} ${y(0)} Z`;
        g += `<path d="${d} ${base}" fill="${s.cor}" fill-opacity="0.18"/>`;
      }
      g += `<path d="${d}" fill="none" stroke="${s.cor}" stroke-width="2.2" stroke-linejoin="round"/>`;
    });
    const passo = Math.max(1, Math.ceil(n / 6));
    (rotulos || []).forEach((r, i) => {
      if (i % passo && i !== n - 1) return;
      g += `<text x="${x(i)}" y="${h - 4}" fill="#8b93a7" font-size="10" text-anchor="middle">${esc(r)}</text>`;
    });
    const leg = series.map((s) => `<span><i style="background:${s.cor}"></i>${esc(s.nome)}</span>`).join("");
    return `<div class="gx-leg">${leg}</div><svg class="gx-svg" viewBox="0 0 ${w} ${h}" role="img">${g}</svg>`;
  }

  function barrasH(itens) {
    const nums = itens.map((i) => (i.n == null ? 0 : Number(i.n)));
    const max = Math.max(1, ...nums);
    return `<div class="gx-hbars">${itens.map((i) => {
      const largura = i.ativo === false || i.n == null ? 0 : (Number(i.n) / max) * 100;
      const valor = i.n == null ? (i.nota || "sem dado") : num(i.n);
      return `<div class="gx-hbar${i.ativo === false ? " off" : ""}"><span>${esc(i.id)}</span><span class="trilha"><i style="width:${largura}%"></i></span><b>${esc(valor)}</b></div>`;
    }).join("")}</div>`;
  }

  function funil(etapas) {
    const base = Math.max(1, ...etapas.map((e) => Number(e.n) || 0));
    return `<ol class="gx-funil">${etapas.map((e, i) => {
      const n = Number(e.n);
      const tem = e.n != null && !Number.isNaN(n);
      const pct = tem ? Math.max(8, (n / base) * 100) : 8;
      const anterior = i ? Number(etapas[i - 1].n) : null;
      const passa = anterior ? Math.round((n / anterior) * 100) + "% do passo anterior" : "chegada";
      return `<li><span>${esc(e.nome)}</span><span class="trilha"><i style="width:${pct}%"></i></span><b>${tem ? num(n) : "sem dado"}</b><small>${tem && i ? passa : ""}</small></li>`;
    }).join("")}</ol>`;
  }

  function gauge(valor, teto) {
    const tem = valor != null && !Number.isNaN(Number(valor));
    const pct = tem ? Math.max(0, Math.min(1, Number(valor) / teto)) : 0;
    const cor = !tem ? "#8b93a7" : pct >= 0.9 ? "#f87171" : pct >= 0.75 ? "#fbbf24" : "#34d399";
    const ang = Math.PI * (1 - pct);
    const x = 80 + Math.cos(ang) * 58;
    const y = 78 - Math.sin(ang) * 58;
    return `<div class="gx-gauge"><svg viewBox="0 0 160 96" role="img" aria-label="Ritmo de envio">
      <path d="M22 78 A58 58 0 0 1 138 78" fill="none" stroke="rgba(255,255,255,.1)" stroke-width="12" stroke-linecap="round"/>
      <path d="M22 78 A58 58 0 0 1 ${x.toFixed(1)} ${y.toFixed(1)}" fill="none" stroke="${cor}" stroke-width="12" stroke-linecap="round"/>
      </svg><div><b>${tem ? num(Math.round(Number(valor))) : "sem dado"}</b><small>de ${num(teto)} por minuto</small></div></div>`;
  }

  function desenhar(d) {
    const banner = $("#demoBanner");
    if (banner) banner.hidden = !d.demo;
    document.body.classList.toggle("modo-demo", !!d.demo);

    const inicio = $("#gx-inicio");
    if (inicio) {
      const vendas = d.vendas_hora && !d.vendas_hora.sem_dado
        ? linha(0, [{ nome: "R$ na hora", cor: "#5eead4", dados: d.vendas_hora.reais || [], area: true }], d.vendas_hora.rotulos, { eixo: (v) => "R$" + Math.round(v) })
        : vazio(d.vendas_hora && d.vendas_hora.motivo);
      const msgs = d.mensagens_min && !d.mensagens_min.sem_dado
        ? linha(0, [
            { nome: "Recebidas", cor: "#67e8f9", dados: d.mensagens_min.recebidas || [] },
            { nome: "Enviadas", cor: "#c4b5fd", dados: d.mensagens_min.enviadas || [] },
          ], d.mensagens_min.rotulos, { h: 150 })
        : vazio(d.mensagens_min && d.mensagens_min.motivo);
      const envio = d.envio || {};
      inicio.innerHTML =
        cartao("Vendas ao longo do dia", "Cada hora, em reais. O detalhe de cada pagamento está em Vendas.", vendas) +
        cartao("Mensagens por minuto", "Última hora. O fio completo está em Mensagens.", msgs) +
        cartao("Envio do robô", "Teto de " + (d.cap_envio_min || 240) + " por minuto.", gauge(envio.agora, envio.teto || d.cap_envio_min || 240) + (envio.motivo ? `<p class="gx-vazio">${esc(envio.motivo)}</p>` : ""));
    }

    const vendasHost = $("#gx-vendas");
    if (vendasHost) {
      const bloco = d.vendas_hora && !d.vendas_hora.sem_dado
        ? linha(0, [
            { nome: "Pagamentos", cor: "#5eead4", dados: d.vendas_hora.n || [], area: true },
          ], d.vendas_hora.rotulos, { h: 200 })
        : vazio(d.vendas_hora && d.vendas_hora.motivo);
      vendasHost.innerHTML = cartao("Vendas no tempo", "Quantos pagamentos caíram em cada hora de hoje.", bloco);
    }

    const funilHost = $("#gx-funil");
    if (funilHost) {
      const f = d.funil || {};
      const miolo = f.sem_dado ? vazio(f.motivo) : funil(f.etapas || []);
      const nota = f.vazamento ? "Onde mais se perde gente: " + f.vazamento + "." : "Caminho de quem chegou pelo anúncio.";
      funilHost.innerHTML = cartao("Funil de hoje", nota, miolo);
    }

    const msgHost = $("#gx-msg");
    if (msgHost) {
      const m = d.mensagens_min || {};
      const miolo = m.sem_dado ? vazio(m.motivo) : linha(0, [
        { nome: "Recebidas", cor: "#67e8f9", dados: m.recebidas || [], area: true },
        { nome: "Enviadas", cor: "#c4b5fd", dados: m.enviadas || [] },
      ], m.rotulos, { h: 200 });
      msgHost.innerHTML = cartao("Mensagens por minuto", "Últimos 60 minutos, somando todos os WhatsApps.", miolo);
    }

    const saude = $("#gx-saude");
    if (saude) {
      const r = d.robo || {};
      const envio = d.envio || {};
      const serie = (envio.serie && envio.serie.length) ? envio.serie : envioAoVivo.map((p) => p.v);
      const rotulos = (envio.rotulos && envio.rotulos.length) ? envio.rotulos : envioAoVivo.map((p) => p.t);
      const ritmo = envio.sem_dado && !serie.length
        ? vazio(envio.motivo)
        : linha(0, [{ nome: "Envios / min", cor: "#5eead4", dados: serie.length ? serie : [envio.agora], area: true }], rotulos, { marca: envio.teto || 240, max: envio.teto || 240, h: 160 });
      const erros = r.sem_dado ? vazio(r.motivo) : linha(0, [{ nome: "Alertas", cor: "#f87171", dados: r.erros_hora || [] }], r.rotulos_hora, { h: 140 });
      const luzes = (r.servicos || []).map((s) => `<span class="gx-luz ${s.ok ? "ok" : "ruim"}">${esc(s.nome)}</span>`).join("");
      saude.innerHTML =
        cartao("Ritmo de envio", "A linha vermelha é o teto de " + (envio.teto || 240) + " mensagens por minuto.", gauge(envio.agora, envio.teto || 240) + ritmo) +
        cartao("Saúde do robô", "Serviços de pé e alertas das últimas 12 horas.", `<div class="gx-luzes">${luzes || ""}</div>` + erros);
    }

    const ativos = $("#gx-ativos");
    if (ativos) {
      const a = d.ativos || {};
      const miolo = a.sem_dado ? vazio(a.motivo) : barrasH(a.paineis || []);
      ativos.innerHTML = cartao("Clientes ativos por painel", "P1, P2, P4, P5 e P6. O P3 está desligado e não entra na conta.", miolo);
    }
  }

  function anotarEnvio(valor) {
    if (valor == null || Number.isNaN(Number(valor))) return;
    const t = new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
    const ultimoP = envioAoVivo[envioAoVivo.length - 1];
    if (ultimoP && ultimoP.t === t) ultimoP.v = Number(valor);
    else envioAoVivo.push({ t, v: Number(valor) });
    if (envioAoVivo.length > 60) envioAoVivo = envioAoVivo.slice(-60);
    if (ultimo && ultimo.envio) {
      ultimo.envio.agora = Number(valor);
      if (!ultimo.envio.serie) desenhar(ultimo);
    }
  }

  async function puxar() {
    try {
      const r = await fetch("/api/graficos", { cache: "no-store", credentials: "same-origin" });
      if (!r.ok) return;
      ultimo = await r.json();
      if (ultimo.envio && ultimo.envio.agora != null && !(ultimo.envio.serie && ultimo.envio.serie.length)) {
        anotarEnvio(ultimo.envio.agora);
      }
      desenhar(ultimo);
    } catch (e) { /* tenta de novo no próximo ciclo */ }
  }

  function ligar() {
    if (timer) return;
    puxar();
    timer = setInterval(() => { if (!document.hidden) puxar(); }, 15000);
    window.addEventListener("painel-envio", (ev) => anotarEnvio(ev.detail));
  }

  window.GraficosAoVivo = { ligar, puxar };
  if (document.getElementById("app") && !document.getElementById("app").hidden) ligar();
  const obs = new MutationObserver(() => {
    const app = document.getElementById("app");
    if (app && !app.hidden) ligar();
  });
  const app = document.getElementById("app");
  if (app) obs.observe(app, { attributes: true, attributeFilter: ["hidden"] });
})();
