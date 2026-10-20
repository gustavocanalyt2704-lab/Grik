/* Ações: buscar cliente, confirmar na tela e mostrar o resultado em frase. */
const Acoes = (() => {
  let pendente = null;
  let opcoes = null;

  function el(id) { return document.getElementById(id); }

  async function abrir() {
    if (!opcoes) await carregarOpcoes();
  }

  async function carregarOpcoes() {
    const r = await fetch("/api/opcoes");
    if (!r.ok) return;
    opcoes = await r.json();
    const painel = el("acaoPainel");
    const app = el("acaoApp");
    painel.innerHTML = (opcoes.paineis || []).map((p) => `<option value="${esc(p.id)}">${esc(p.nome)}${p.pronto ? "" : " (ainda não configurado)"}</option>`).join("");
    app.innerHTML = (opcoes.apps || []).map((nome) => `<option value="${esc(nome)}">${esc(nome)}</option>`).join("");
    atualizarTelas();
    painel.onchange = atualizarTelas;
  }

  function atualizarTelas() {
    const id = el("acaoPainel").value;
    const item = (opcoes.paineis || []).find((p) => p.id === id);
    const n = item ? item.telas : 4;
    el("acaoTelas").textContent = `Liberar ${n} telas`;
  }

  function consulta() {
    return el("acaoBusca").value.trim();
  }

  async function buscar() {
    const q = consulta();
    el("acaoResultado").hidden = true;
    el("confirma").hidden = true;
    if (!q) {
      el("acaoBuscaMsg").textContent = "Digite o telefone ou o usuário.";
      return;
    }
    el("acaoBuscaMsg").textContent = "Buscando…";
    const r = await fetch("/api/cliente?q=" + encodeURIComponent(q));
    if (r.status === 401) { if (window.voltarAoLogin) voltarAoLogin("Sua sessão terminou. Entre de novo."); return; }
    const f = await r.json();
    el("acaoBuscaMsg").textContent = f.frase || "";
    el("acaoFicha").innerHTML = fichaHtml(f);
    if (f.painel_sugerido && el("acaoPainel").querySelector(`option[value="${CSS.escape(f.painel_sugerido)}"]`)) {
      el("acaoPainel").value = f.painel_sugerido;
      atualizarTelas();
    }
  }

  function fichaHtml(f) {
    if (!f || !f.ok) return "";
    const linhas = [
      ["Usuário", f.usuario || "—"],
      ["Plano", f.plano || "—"],
      ["Vencimento", f.vencimento || "—"],
      ["Telas", f.telas == null ? "—" : String(f.telas)],
      ["App", f.app || "—"],
      ["WhatsApp da conversa", f.linha || "sem número"],
      ["Última conversa", f.ultima || "Sem conversa recente no painel."],
    ];
    const aviso = f.protegido ? `<p class="nota">Esse número é protegido. Dá para ver, mas os botões não mexem nele.</p>` : "";
    const pausa = f.pausado ? `<p class="nota">O robô está pausado só para este cliente.</p>` : "";
    return `<dl class="ficha">${linhas.map(([k, v]) => `<div><dt>${esc(k)}</dt><dd class="${k === "WhatsApp da conversa" && v === "sem número" ? "mudo" : ""}">${esc(v)}</dd></div>`).join("")}</dl>${aviso}${pausa}`;
  }

  async function pedir(botao) {
    const q = consulta();
    if (!q) {
      el("acaoBuscaMsg").textContent = "Digite o telefone ou o usuário.";
      return;
    }
    pendente = {
      acao: botao.dataset.acao,
      q,
      dias: Number(botao.dataset.dias || 30),
      app: el("acaoApp").value,
      painel: el("acaoPainel").value,
      confirmar: false,
    };
    await enviar(false);
  }

  async function enviar(confirmar) {
    if (!pendente) return;
    pendente.confirmar = confirmar;
    el("acaoResultado").hidden = true;
    const r = await fetch("/api/acao", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(pendente),
    });
    if (r.status === 401) { if (window.voltarAoLogin) voltarAoLogin("Sua sessão terminou. Entre de novo."); return; }
    const corpo = await r.json();
    if (corpo.precisa_confirmar) {
      el("confirmaFrase").textContent = corpo.frase || "Confirmar?";
      el("confirma").hidden = false;
      if (corpo.ficha) el("acaoFicha").innerHTML = fichaHtml(corpo.ficha);
      return;
    }
    el("confirma").hidden = true;
    const box = el("acaoResultado");
    box.hidden = false;
    box.textContent = corpo.frase || "Pronto.";
    box.className = "acao-resultado " + (corpo.ok ? "ok" : "ruim");
    if (corpo.ficha) el("acaoFicha").innerHTML = fichaHtml(corpo.ficha);
    pendente = null;
  }

  document.addEventListener("click", (ev) => {
    const botao = ev.target.closest("#vista-acoes [data-acao]");
    if (botao) { ev.preventDefault(); pedir(botao); }
  });
  document.addEventListener("DOMContentLoaded", () => {});
  const buscarBtn = el("acaoBuscar");
  if (buscarBtn) buscarBtn.addEventListener("click", buscar);
  const sim = el("confirmaSim");
  const nao = el("confirmaNao");
  if (sim) sim.addEventListener("click", () => enviar(true));
  if (nao) nao.addEventListener("click", () => { el("confirma").hidden = true; pendente = null; });
  const campo = el("acaoBusca");
  if (campo) campo.addEventListener("keydown", (ev) => { if (ev.key === "Enter") { ev.preventDefault(); buscar(); } });

  return { abrir };
})();
