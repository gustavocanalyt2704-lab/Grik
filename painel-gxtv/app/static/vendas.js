/* VENDAS_1110 — aba Vendas: venda nova x renovação (/api/vendas?dia=AAAA-MM-DD) */
window.VendasNR = (function () {
  const brl = (v) => (v == null ? "—" : "R$ " + Number(v).toFixed(2).replace(".", ","));
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  let dia = "", timer = null, filtro = "todos";
  const hojeISO = () => new Date(Date.now() - 3 * 3600e3).toISOString().slice(0, 10);
  function moldura(box) {
    if (box.querySelector(".vd-topo")) return;
    box.innerHTML = `<div class="vd-topo"><h2>Vendas</h2>
      <input type="date" id="vdDia"><button type="button" id="vdHoje">Hoje</button>
      <span class="vd-filtro"><button type="button" data-vf="todos" class="on">Todas</button><button type="button" data-vf="venda">Novas</button><button type="button" data-vf="renovacao">Renovações</button></span>
      <span id="vdInfo" class="vd-info"></span></div><div id="vdCorpo"><p class="vd-nota">Carregando…</p></div>`;
    const inp = box.querySelector("#vdDia");
    inp.value = dia || hojeISO();
    inp.addEventListener("change", () => { dia = inp.value; atualizar(); });
    box.querySelector("#vdHoje").addEventListener("click", () => { dia = ""; inp.value = hojeISO(); atualizar(); });
    box.querySelectorAll("[data-vf]").forEach((b) => b.addEventListener("click", () => {
      filtro = b.dataset.vf; box.querySelectorAll("[data-vf]").forEach((x) => x.classList.toggle("on", x === b)); atualizar();
    }));
  }
  async function atualizar() {
    const box = document.getElementById("vendasnr-corpo");
    if (!box) return;
    moldura(box);
    let r;
    try {
      const resp = await fetch("/api/vendas" + (dia ? "?dia=" + dia : ""), { credentials: "same-origin" });
      r = await resp.json();
    } catch (e) { box.querySelector("#vdCorpo").innerHTML = `<p class="vd-nota">Falha ao carregar.</p>`; return; }
    if (r.ok === false && !r.dia) { box.querySelector("#vdCorpo").innerHTML = `<p class="vd-nota">Sem acesso.</p>`; return; }
    const idade = r.marcador_idade_s;
    box.querySelector("#vdInfo").textContent = `atualizado ${r.gerado}` + (idade != null && idade > 180 ? ` · marcador de venda nova parado há ${Math.round(idade / 60)} min` : "") + (r.erro ? ` · ${r.erro}` : "");
    const insts = r.por_instancia.map((i) => `<div class="vd-inst"><b>${esc(i.instancia)}</b><span>${i.n}</span><small>${brl(i.reais)}</small></div>`).join("");
    const linhas = r.lista.filter((i) => filtro === "todos" || i.tipo === filtro).map((i) => `<tr class="vd-${i.tipo}">
      <td>${esc(i.pix || "—")}</td><td>${esc(i.hora)}</td><td>${esc(i.telefone)}</td><td>${brl(i.valor)}</td>
      <td><span class="vd-tag">${i.tipo === "venda" ? "Venda nova" : "Renovação"}</span></td><td>${esc(i.instancia)}</td></tr>`).join("");
    box.querySelector("#vdCorpo").innerHTML = `
      <div class="vd-kpis">
        <div class="vd-kpi vd-k-nova"><small>Vendas novas</small><b>${r.novas.n}</b><span>${brl(r.novas.reais)}</span></div>
        <div class="vd-kpi vd-k-renov"><small>Renovações</small><b>${r.renovacoes.n}</b><span>${brl(r.renovacoes.reais)}${r.renovacoes.sem_valor ? ` · ${r.renovacoes.sem_valor} sem valor` : ""}</span></div>
        <div class="vd-kpi"><small>Total</small><b>${r.total.n}</b><span>${brl(r.total.reais)}</span></div>
      </div>
      <h3>Vendas novas por instância</h3><div class="vd-insts">${insts}</div>
      <h3>Vendas do dia</h3>
      <div class="vd-tab"><table><thead><tr><th>Pix chegou</th><th>Renovado às</th><th>Telefone</th><th>Valor</th><th>Tipo</th><th>Instância</th></tr></thead>
      <tbody>${linhas || `<tr><td colspan="6" class="vd-nota">Nada neste dia.</td></tr>`}</tbody></table></div>`;
  }
  function abrir() { atualizar(); if (!timer) timer = setInterval(() => { if (!document.hidden) atualizar(); }, 20000); }
  function fechar() { if (timer) { clearInterval(timer); timer = null; } }
  return { abrir, fechar, atualizar };
})();
