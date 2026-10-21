/* Gráficos ao vivo com ECharts. Lê /api/graficos e o ritmo do stream. */
(function () {
  const $ = (s) => document.querySelector(s);
  let ultimo = null;
  let envioAoVivo = [];
  let timer = null;
  const charts = new Map();

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  function num(v) {
    if (v == null || Number.isNaN(Number(v))) return "sem dado";
    return Number(v).toLocaleString("pt-BR");
  }
  function paleta() {
    const claro = document.documentElement.dataset.tema === "claro";
    const css = getComputedStyle(document.documentElement);
    const pegar = (nome, fb) => (css.getPropertyValue(nome) || fb).trim();
    return {
      claro,
      text: pegar("--muted", claro ? "#71717a" : "#a1a1aa"),
      ink: pegar("--text", claro ? "#18181b" : "#fafafa"),
      line: claro ? "rgba(24,24,27,.08)" : "rgba(255,255,255,.08)",
      panel: pegar("--surface", claro ? "#fff" : "#141418"),
      series: ["#8b7cf6", "#2dd4bf", "#60a5fa", "#fbbf24", "#fb7185"],
    };
  }
  function cartao(titulo, sub, miolo) {
    return `<article class="gx-card"><header><h3>${esc(titulo)}</h3><p>${esc(sub || "")}</p></header>${miolo}</article>`;
  }
  function vazio(motivo) {
    return `<div class="gx-vazio"><b>Sem série nesta tela</b><span>${esc(motivo || "sem dado")}</span></div>`;
  }
  function baseOpt(p) {
    return {
      animationDuration: 700,
      animationDurationUpdate: 450,
      animationEasing: "cubicOut",
      textStyle: { fontFamily: "Inter, sans-serif" },
      tooltip: {
        trigger: "axis",
        backgroundColor: p.panel,
        borderColor: p.line,
        textStyle: { color: p.ink, fontSize: 12 },
      },
      grid: { left: 46, right: 16, top: 32, bottom: 28 },
      legend: { top: 0, icon: "circle", itemWidth: 8, itemHeight: 8, textStyle: { color: p.text, fontSize: 11 } },
    };
  }
  function eixo(p, rotulos) {
    return {
      xAxis: {
        type: "category",
        data: rotulos || [],
        axisLabel: { color: p.text, fontSize: 10, hideOverlap: true },
        axisLine: { lineStyle: { color: p.line } },
        axisTick: { show: false },
      },
      yAxis: {
        type: "value",
        axisLabel: { color: p.text, fontSize: 10 },
        splitLine: { lineStyle: { color: p.line } },
      },
    };
  }
  function serieLinha(s, i, p, tipo) {
    const cor = s.cor || p.series[i % p.series.length];
    return {
      name: s.nome,
      type: tipo || "line",
      data: s.dados,
      smooth: true,
      showSymbol: false,
      barMaxWidth: 16,
      itemStyle: { color: cor, borderRadius: tipo === "bar" ? [6, 6, 0, 0] : 0 },
      lineStyle: { width: 2, color: cor },
      areaStyle: s.area && window.echarts ? {
        color: new window.echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: cor },
          { offset: 1, color: "transparent" },
        ]),
        opacity: 0.28,
      } : undefined,
      markLine: s.marca == null ? undefined : {
        symbol: "none",
        label: { formatter: s.marcaNome || ("teto " + s.marca), color: p.series[4], fontSize: 10 },
        lineStyle: { color: p.series[4], type: "dashed" },
        data: [{ yAxis: s.marca }],
      },
    };
  }
  function plot(el, option) {
    if (!el || !window.echarts) return;
    let c = charts.get(el);
    if (!c) {
      c = echarts.init(el, null, { renderer: "svg" });
      charts.set(el, c);
    }
    c.setOption(option, true);
  }
  function hostPlot(id) {
    return `<div class="gx-plot" id="${id}"></div>`;
  }
  function spark(alvo, dados, cor) {
    const el = document.querySelector(`.p11-spark[data-spark="${alvo}"]`);
    if (!el) return;
    const nums = (dados || []).filter((v) => v != null && !Number.isNaN(Number(v))).map(Number);
    if (nums.length < 2) { el.innerHTML = ""; return; }
    const w = 88, h = 28;
    const min = Math.min(...nums), max = Math.max(...nums), span = max - min || 1;
    const pts = nums.map((v, i) => [(i / (nums.length - 1)) * w, h - 2 - ((v - min) / span) * (h - 4)]);
    const d = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
    el.innerHTML = `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" aria-hidden="true"><path d="${d} L${w} ${h} L0 ${h} Z" fill="${cor}" opacity="0.16"/><path d="${d}" fill="none" stroke="${cor}" stroke-width="1.6" stroke-linecap="round"/></svg>`;
  }

  function desenhar(d) {
    const banner = $("#demoBanner");
    if (banner) banner.hidden = !d.demo;
    document.body.classList.toggle("modo-demo", !!d.demo);
    const p = paleta();

    const inicio = $("#gx-inicio");
    if (inicio) {
      const envio = d.envio || {};
      inicio.innerHTML =
        cartao("Vendas ao longo do dia", "Cada hora, em reais. O detalhe de cada pagamento está em Vendas.", d.vendas_hora && !d.vendas_hora.sem_dado ? hostPlot("gx-plot-vendas-dia") : vazio(d.vendas_hora && d.vendas_hora.motivo)) +
        cartao("Mensagens por minuto", "Última hora. O fio completo está em Mensagens.", d.mensagens_min && !d.mensagens_min.sem_dado ? hostPlot("gx-plot-msgs-ini") : vazio(d.mensagens_min && d.mensagens_min.motivo)) +
        cartao("Envio do robô", "Teto de " + (d.cap_envio_min || 240) + " por minuto.", envio.sem_dado && envio.agora == null ? vazio(envio.motivo) : hostPlot("gx-plot-envio-ini"));
      if (d.vendas_hora && !d.vendas_hora.sem_dado) {
        plot($("#gx-plot-vendas-dia"), Object.assign(baseOpt(p), eixo(p, d.vendas_hora.rotulos), {
          series: [serieLinha({ nome: "R$ na hora", dados: d.vendas_hora.reais || [], area: true }, 0, p)],
        }));
      }
      if (d.mensagens_min && !d.mensagens_min.sem_dado) {
        plot($("#gx-plot-msgs-ini"), Object.assign(baseOpt(p), eixo(p, d.mensagens_min.rotulos), {
          series: [
            serieLinha({ nome: "Recebidas", dados: d.mensagens_min.recebidas || [], area: true }, 0, p),
            serieLinha({ nome: "Enviadas", dados: d.mensagens_min.enviadas || [] }, 1, p),
          ],
        }));
      }
      if (!(envio.sem_dado && envio.agora == null)) {
        const serie = (envio.serie && envio.serie.length) ? envio.serie : envioAoVivo.map((x) => x.v);
        const rotulos = (envio.rotulos && envio.rotulos.length) ? envio.rotulos : envioAoVivo.map((x) => x.t);
        plot($("#gx-plot-envio-ini"), Object.assign(baseOpt(p), eixo(p, rotulos), {
          series: [serieLinha({ nome: "Envios / min", dados: serie.length ? serie : [envio.agora], area: true, marca: envio.teto || 240, marcaNome: "teto " + (envio.teto || 240) }, 1, p)],
        }));
      }
    }

    const vendasHost = $("#gx-vendas");
    if (vendasHost) {
      vendasHost.innerHTML = cartao("Vendas no tempo", "Quantos pagamentos caíram em cada hora de hoje.", d.vendas_hora && !d.vendas_hora.sem_dado ? hostPlot("gx-plot-vendas") : vazio(d.vendas_hora && d.vendas_hora.motivo));
      if (d.vendas_hora && !d.vendas_hora.sem_dado) {
        plot($("#gx-plot-vendas"), Object.assign(baseOpt(p), eixo(p, d.vendas_hora.rotulos), {
          series: [serieLinha({ nome: "Pagamentos", dados: d.vendas_hora.n || [], area: true }, 0, p)],
        }));
      }
    }

    const funilHost = $("#gx-funil");
    if (funilHost) {
      const f = d.funil || {};
      const nota = f.vazamento ? "Onde mais se perde gente: " + f.vazamento + "." : "Caminho de quem chegou pelo anúncio.";
      funilHost.innerHTML = cartao("Funil de hoje", nota, f.sem_dado ? vazio(f.motivo) : hostPlot("gx-plot-funil"));
      if (!f.sem_dado) {
        plot($("#gx-plot-funil"), {
          animationDuration: 700,
          tooltip: { trigger: "item", backgroundColor: p.panel, borderColor: p.line, textStyle: { color: p.ink } },
          series: [{
            type: "funnel",
            left: "8%",
            width: "76%",
            top: 8,
            bottom: 8,
            minSize: "18%",
            sort: "descending",
            gap: 6,
            label: { color: p.ink, fontSize: 12, fontFamily: "Inter, sans-serif" },
            itemStyle: { borderWidth: 0 },
            data: (f.etapas || []).map((e, i) => ({ name: e.nome, value: e.n == null ? 0 : Number(e.n), itemStyle: { color: p.series[i % p.series.length] } })),
          }],
        });
      }
    }

    const msgHost = $("#gx-msg");
    if (msgHost) {
      const m = d.mensagens_min || {};
      msgHost.innerHTML = cartao("Mensagens por minuto", "Últimos 60 minutos, somando todos os WhatsApps.", m.sem_dado ? vazio(m.motivo) : hostPlot("gx-plot-msg"));
      if (!m.sem_dado) {
        plot($("#gx-plot-msg"), Object.assign(baseOpt(p), eixo(p, m.rotulos), {
          series: [
            serieLinha({ nome: "Recebidas", dados: m.recebidas || [], area: true }, 0, p),
            serieLinha({ nome: "Enviadas", dados: m.enviadas || [] }, 1, p),
          ],
        }));
      }
    }

    const saude = $("#gx-saude");
    if (saude) {
      const r = d.robo || {};
      const envio = d.envio || {};
      const serie = (envio.serie && envio.serie.length) ? envio.serie : envioAoVivo.map((x) => x.v);
      const rotulos = (envio.rotulos && envio.rotulos.length) ? envio.rotulos : envioAoVivo.map((x) => x.t);
      const luzes = (r.servicos || []).map((s) => `<span class="gx-luz ${s.ok ? "ok" : "ruim"}">${esc(s.nome)}</span>`).join("");
      saude.innerHTML =
        cartao("Ritmo de envio", "A linha vermelha é o teto de " + (envio.teto || 240) + " mensagens por minuto.", (envio.sem_dado && !serie.length) ? vazio(envio.motivo) : hostPlot("gx-plot-ritmo")) +
        cartao("Saúde do robô", "Serviços de pé e alertas das últimas 12 horas.", `<div class="gx-luzes">${luzes || ""}</div>` + (r.sem_dado ? vazio(r.motivo) : hostPlot("gx-plot-erros")));
      if (!(envio.sem_dado && !serie.length)) {
        plot($("#gx-plot-ritmo"), Object.assign(baseOpt(p), eixo(p, rotulos), {
          series: [serieLinha({ nome: "Envios / min", dados: serie.length ? serie : [envio.agora], area: true, marca: envio.teto || 240, marcaNome: "teto " + (envio.teto || 240) }, 1, p)],
        }));
      }
      if (!r.sem_dado) {
        plot($("#gx-plot-erros"), Object.assign(baseOpt(p), eixo(p, r.rotulos_hora), {
          series: [serieLinha({ nome: "Alertas", dados: r.erros_hora || [], cor: p.series[4] }, 4, p)],
        }));
      }
    }

    const ativos = $("#gx-ativos");
    if (ativos) {
      const a = d.ativos || {};
      ativos.innerHTML = cartao("Clientes ativos por painel", "P1, P2, P4, P5 e P6. O P3 está desligado e não entra na conta.", a.sem_dado ? vazio(a.motivo) : hostPlot("gx-plot-ativos"));
      if (!a.sem_dado) {
        const itens = a.paineis || [];
        plot($("#gx-plot-ativos"), Object.assign(baseOpt(p), {
          grid: { left: 36, right: 16, top: 12, bottom: 24 },
          xAxis: { type: "category", data: itens.map((i) => i.id), axisLabel: { color: p.text }, axisLine: { lineStyle: { color: p.line } }, axisTick: { show: false } },
          yAxis: { type: "value", axisLabel: { color: p.text }, splitLine: { lineStyle: { color: p.line } } },
          series: [{
            type: "bar",
            barMaxWidth: 28,
            data: itens.map((i) => ({
              value: i.ativo === false || i.n == null ? null : Number(i.n),
              itemStyle: { color: i.ativo === false || i.n == null ? "#3f3f46" : p.series[0], borderRadius: [6, 6, 0, 0] },
            })),
          }],
        }));
      }
    }

    if (d.vendas_hora && !d.vendas_hora.sem_dado) {
      spark("vendas", d.vendas_hora.reais, p.series[0]);
      spark("novas", d.vendas_hora.n, p.series[1]);
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
      if (ultimo.envio && ultimo.envio.agora != null && !(ultimo.envio.serie && ultimo.envio.serie.length)) anotarEnvio(ultimo.envio.agora);
      desenhar(ultimo);
    } catch (e) { /* tenta de novo no próximo ciclo */ }
  }

  function ligar() {
    if (timer) return;
    puxar();
    timer = setInterval(() => { if (!document.hidden) puxar(); }, 15000);
    window.addEventListener("painel-envio", (ev) => anotarEnvio(ev.detail));
    window.addEventListener("gx-tema", () => { charts.forEach((c) => c.dispose()); charts.clear(); if (ultimo) desenhar(ultimo); });
    window.addEventListener("resize", () => charts.forEach((c) => c.resize()));
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
