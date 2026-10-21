"""Registro único de métricas — fonte de verdade para tooltips e drill-down.

Cada métrica declara: nome, definição, fonte, fórmula, timezone, janela, last_update.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.core.timezone import TZ_NAME, agora, iso_bahia


class MetricDef(BaseModel):
    id: str
    name: str
    definition: str
    source: str
    formula: str
    timezone: str = TZ_NAME
    default_window: str = "hoje"
    module: str  # inicio | atendimento | comercial | operacao | robo | espelho
    drilldown: str | None = None  # endpoint relativo
    unit: str | None = None
    notes: str | None = None
    last_update: str | None = None


# Registro canônico F1 — módulos F2–F7 ampliam sem duplicar definição.
REGISTRY: dict[str, MetricDef] = {}


def _reg(**kwargs: Any) -> MetricDef:
    m = MetricDef(**kwargs)
    REGISTRY[m.id] = m
    return m


# --- Início ---
_reg(
    id="inicio.faturamento",
    name="Faturamento (hoje)",
    definition="Faturamento do dia civil America/Bahia segundo o Gestor IPTV (autoridade).",
    source="gestor /api/manager/today-summary (cache)",
    formula="valor Gestor do dia; se ausente → indisponível (nunca 0 inventado)",
    module="inicio",
    unit="R$",
    drilldown="/api/v2/drilldown",
    notes="Gestor-first. Sem Bearer/cache → unavailable + last update.",
)
_reg(
    id="inicio.renovacoes",
    name="Renovações (hoje)",
    definition="Renovações confirmadas hoje no Gestor (renewals-today).",
    source="gestor /api/expiring/renewals-today (cache)",
    formula="COUNT(renewals-today)",
    module="inicio",
    unit="un",
    drilldown="/api/v2/drilldown",
)
_reg(
    id="inicio.vencem_hoje",
    name="Vencem hoje",
    definition="Clientes com vencimento no dia civil Bahia (Gestor). Detalhe: total / já renovaram / pendentes.",
    source="gestor /api/expiring/today + renewals-today",
    formula="total=|vence_hoje|; renovaram=renewals; pendentes=total-renovaram",
    module="inicio",
    unit="un",
    drilldown="/api/v2/drilldown",
)
_reg(
    id="inicio.atendidos",
    name="Atendidos hoje",
    definition="Conversas com pelo menos um envio (outbound) no dia civil Bahia, via webhook/espelho.",
    source="webhook queue.jsonl",
    formula="COUNT DISTINCT conversation_id WHERE from_me AND ts ∈ hoje Bahia",
    module="inicio",
    unit="conv",
    drilldown="/api/v2/drilldown",
)
_reg(
    id="inicio.esperando_15min",
    name="Esperando >15 min (agora)",
    definition="Clientes cuja última fala é inbound e ainda sem resposta há mais de 15 minutos — contagem AGORA.",
    source="webhook queue.jsonl (estado por conversa)",
    formula="COUNT(conv WHERE last_in > last_out AND agora-last_in >= 15min)",
    module="inicio",
    unit="cli",
    drilldown="/api/v2/drilldown",
)
_reg(
    id="inicio.clientes_min",
    name="Clientes / min",
    definition="Taxa de clientes únicos inbound na janela recente (webhook), normalizada por minuto.",
    source="webhook queue.jsonl",
    formula="DISTINCT phones inbound / (janela_min)",
    module="inicio",
    unit="cli/min",
    drilldown="/api/v2/drilldown",
)
_reg(
    id="inicio.entrada_viva",
    name="Entrada ao vivo",
    definition="Mensagens de clientes recebidas via webhook/espelho nos últimos minutos.",
    source="webhook queue.jsonl",
    formula="COUNT(msgs inbound WHERE ts >= agora-5min)",
    module="inicio",
    drilldown="/api/v2/drilldown",
    unit="msgs",
)
_reg(
    id="inicio.log_operacional",
    name="Log operacional ao vivo",
    definition="Eventos do robô e do painel (POLL, envios, alertas) em tempo quase real via SSE.",
    source="live.log + espelho eventos",
    formula="tail stream (SSE /api/v2/inicio/log/stream)",
    module="inicio",
    drilldown="/api/v2/drilldown",
)
_reg(
    id="inicio.saude_espelho",
    name="Saúde do espelho",
    definition="Lag e cobertura do espelho alimentado pelo webhook.",
    source="espelho metadados + mtime fila webhook",
    formula="lag_s = agora - max(msg.ts|mtime); cobertura = msgs_com_texto / eventos",
    module="inicio",
    unit="s",
    drilldown="/api/v2/drilldown",
)
_reg(
    id="inicio.kpis_gestor",
    name="Pacote KPIs Gestor (Início)",
    definition="Envelope agregado faturamento/renovações/vencem hoje — uso interno do módulo Início.",
    source="gestor cache",
    formula="fetch_kpis_comerciais()",
    module="inicio",
)

# --- Atendimento ---
_reg(
    id="atendimento.funil",
    name="Funil de atendimento",
    definition="Estágios clicáveis do atendimento no período (sem status de abandono).",
    source="espelho.conversas agregadas",
    formula="bucket por estágio operacional (novo→em_atendimento→aguardando→resolvido)",
    module="atendimento",
    drilldown="/api/v2/drilldown/atendimento.funil",
)
_reg(
    id="atendimento.t_resposta_media",
    name="Tempo de resposta — média",
    definition="Média do tempo até a 1ª resposta humana/robô, agrupando mensagens seguidas do mesmo lado.",
    source="espelho.mensagens",
    formula="AVG(gap) onde gap = ts_1ª_resposta - ts_última_msg_cliente_do_bloco",
    module="atendimento",
    unit="s",
    drilldown="/api/v2/drilldown/atendimento.t_resposta",
)
_reg(
    id="atendimento.t_resposta_mediana",
    name="Tempo de resposta — mediana",
    definition="Mediana do tempo de resposta (mesmo agrupamento de msgs seguidas).",
    source="espelho.mensagens",
    formula="MEDIAN(gap)",
    module="atendimento",
    unit="s",
    drilldown="/api/v2/drilldown/atendimento.t_resposta",
)
_reg(
    id="atendimento.t_resposta_p95",
    name="Tempo de resposta — P95",
    definition="Percentil 95 do tempo de resposta.",
    source="espelho.mensagens",
    formula="P95(gap)",
    module="atendimento",
    unit="s",
    drilldown="/api/v2/drilldown/atendimento.t_resposta",
)
_reg(
    id="atendimento.t_resposta_max",
    name="Tempo de resposta — máximo",
    definition="Maior tempo de resposta no período.",
    source="espelho.mensagens",
    formula="MAX(gap)",
    module="atendimento",
    unit="s",
    drilldown="/api/v2/drilldown/atendimento.t_resposta",
)

# --- Comercial (Gestor-first) ---
_reg(
    id="comercial.vendas",
    name="Vendas (Gestor)",
    definition="Vendas do dia segundo o Gestor IPTV. Inclui instâncias WhatsApp 3619 e 0837.",
    source="gestor-iptv-1.emergent.host (cache)",
    formula="SUM(vendas Gestor no dia civil Bahia filtradas por WhatsApp)",
    module="comercial",
    unit="R$",
    drilldown="/api/v2/drilldown/comercial.vendas",
    notes="Se Gestor cair → indisponível + last update; nunca 0 inventado.",
)
_reg(
    id="comercial.vencem_hoje",
    name="Vencem hoje",
    definition="Clientes com vencimento no dia civil Bahia: total, renovaram, pendentes.",
    source="Gestor (autoridade) + cache local",
    formula="total = |vence_hoje|; renovaram = pagos no dia; pendentes = total - renovaram",
    module="comercial",
    drilldown="/api/v2/drilldown/comercial.vencem_hoje",
)
_reg(
    id="comercial.dist_whatsapp",
    name="Distribuição WhatsApp",
    definition="Vendas/atendimentos por número WhatsApp (3619, 0837, demais).",
    source="Gestor + espelho instância",
    formula="GROUP BY instancia_whatsapp",
    module="comercial",
    drilldown="/api/v2/drilldown/comercial.dist_whatsapp",
)
_reg(
    id="comercial.funil_vendas",
    name="Funil de vendas",
    definition="Por número de venda (3619, 0837, 3166): leads novos, aparelho, app enviado, teste entregue, funcionou e pago. Taxa e tempo médio até o teste. Contador de mensagem de cliente sem resposta há mais de 3 minutos — tem que ficar em zero, com alerta no Telegram.",
    source="funil_eventos.jsonl + webhook",
    formula="contagem cumulativa por conversa; taxa = testes/leads; tempo = média(ts_teste - ts_lead); sem_resposta = inbound sem outbound há > 180s",
    module="comercial",
    drilldown="/api/v2/drilldown/comercial.funil_vendas",
    notes="Sem eventos a métrica fica indisponível. Zero no contador de 3 min só aparece quando a fonte existe e não há pendência.",
)

# --- Operação ---
_reg(
    id="operacao.problemas",
    name="Problemas reportados",
    definition="Problemas no período vs ontem e vs média 7 dias.",
    source="espelho etiquetas/problemas",
    formula="COUNT(problemas); delta_ontem; media_7d",
    module="operacao",
    drilldown="/api/v2/drilldown/operacao.problemas",
)
_reg(
    id="operacao.correlacoes",
    name="Correlações app × aparelho × horário",
    definition="Cruzamento de problemas/falhas por app, aparelho e hora Bahia.",
    source="espelho agregações",
    formula="heatmap COUNT GROUP BY app, aparelho, hour(America/Bahia)",
    module="operacao",
    drilldown="/api/v2/drilldown/operacao.correlacoes",
)

# --- Robô ---
_reg(
    id="robo.ocupadas",
    name="Conversas ocupadas",
    definition="Conversas que o robô está processando agora (POLL ocupadas).",
    source="live.log POLL",
    formula="último valor ocupadas=N do POLL",
    module="robo",
)
_reg(
    id="robo.envios",
    name="Envios do robô",
    definition="Mensagens enviadas pelo robô no período.",
    source="espelho outbound autor=robô",
    formula="COUNT(outbound robô)",
    module="robo",
    drilldown="/api/v2/drilldown/robo.envios",
)

# --- Espelho ---
_reg(
    id="espelho.lag",
    name="Lag do espelho",
    definition="Atraso entre agora e a última mensagem espelhada.",
    source="espelho.mensagens",
    formula="agora - max(ts)",
    module="espelho",
    unit="s",
)
_reg(
    id="espelho.cobertura",
    name="Cobertura do webhook",
    definition="Proporção de eventos com texto/messageId (webhook magro vs completo).",
    source="receiver + espelho",
    formula="msgs_com_texto / eventos_recebidos",
    module="espelho",
    unit="%",
)


def list_metrics(module: str | None = None) -> list[MetricDef]:
    items = list(REGISTRY.values())
    if module:
        items = [m for m in items if m.module == module]
    return sorted(items, key=lambda m: (m.module, m.id))


def get_metric(metric_id: str) -> MetricDef | None:
    return REGISTRY.get(metric_id)


def registry_payload() -> dict[str, Any]:
    stamp = iso_bahia(agora())
    metrics = []
    for m in list_metrics():
        d = m.model_dump()
        d["last_update"] = d.get("last_update") or stamp
        metrics.append(d)
    return {
        "timezone": TZ_NAME,
        "count": len(metrics),
        "generated_at": stamp,
        "metrics": metrics,
    }


class GlobalFilters(BaseModel):
    periodo: str = "hoje"
    numero: str | None = None  # WhatsApp instance / final
    atendente: str | None = None
    app: str | None = None
    aparelho: str | None = None


class FilterOptions(BaseModel):
    periodos: list[dict[str, str]] = Field(
        default_factory=lambda: [
            {"id": "hoje", "label": "Hoje"},
            {"id": "ontem", "label": "Ontem"},
            {"id": "7d", "label": "7 dias"},
            {"id": "30d", "label": "30 dias"},
        ]
    )
    numeros: list[dict[str, str]] = Field(default_factory=list)
    atendentes: list[dict[str, str]] = Field(default_factory=list)
    apps: list[dict[str, str]] = Field(default_factory=list)
    aparelhos: list[dict[str, str]] = Field(default_factory=list)
