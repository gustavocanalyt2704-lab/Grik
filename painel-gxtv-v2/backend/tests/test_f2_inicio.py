"""Testes F2 — Início KPIs, espelho, telefone, Gestor never-zero, seed gate."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.metrics_registry import REGISTRY, get_metric
from app.core.states import MetricState
from app.core.timezone import telefone_final
from app.sources import espelho, seed
from app.sources.gestor import extrair_kpi
from app.core.states import MetricEnvelope, SourceRef
from app.services import inicio as inicio_svc


class TestRegistryF2(unittest.TestCase):
    def test_kpis_inicio_registrados(self):
        for mid in (
            "inicio.faturamento",
            "inicio.renovacoes",
            "inicio.vencem_hoje",
            "inicio.atendidos",
            "inicio.esperando_15min",
            "inicio.clientes_min",
            "inicio.entrada_viva",
            "inicio.log_operacional",
            "inicio.saude_espelho",
        ):
            self.assertIsNotNone(get_metric(mid), mid)

    def test_sem_abandonado(self):
        blob = str({k: v.model_dump() for k, v in REGISTRY.items()}).casefold()
        self.assertNotIn("abandonado", blob)


class TestEspelhoMetrics(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.queue = Path(self.tmp.name) / "queue.jsonl"
        now = time.time()
        rows = [
            {
                "telefone": "557799991111",
                "conversa": "c1",
                "nome": "Ana",
                "from_me": False,
                "text": "oi",
                "timestamp": now - 120,
                "instancia": "3619",
            },
            {
                "telefone": "557799991111",
                "conversa": "c1",
                "from_me": True,
                "text": "olá",
                "timestamp": now - 60,
                "instancia": "3619",
            },
            {
                "telefone": "557799992222",
                "conversa": "c2",
                "nome": "Bob",
                "from_me": False,
                "text": "ajuda",
                "timestamp": now - 20 * 60,
                "instancia": "0837",
            },
            {
                "telefone": "557799993333",
                "conversa": "c3",
                "from_me": False,
                "text": "renovar",
                "timestamp": now - 30,
                "instancia": "3619",
            },
        ]
        with self.queue.open("w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")

        self.env = {
            "WEBHOOK_QUEUE": str(self.queue),
            "ESPELHO_DIR": str(Path(self.tmp.name) / "espelho_missing"),
            "LIVE_LOG": str(Path(self.tmp.name) / "missing.log"),
            "PAINEL_V2_SEED": "0",
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_entrada_viva(self):
        with mock.patch.dict(os.environ, self.env, clear=False):
            # reload path constants via direct call after patching module attrs
            espelho.WEBHOOK_QUEUE = self.queue
            env = espelho.entrada_ao_vivo(300)
            self.assertEqual(env.state, MetricState.OK)
            assert isinstance(env.value, list)
            phones = {r["phone_final"] for r in env.value}
            self.assertIn("final 1111", phones)
            self.assertIn("final 3333", phones)
            # c2 is 20min old — fora da janela 5min
            self.assertNotIn("final 2222", phones)

    def test_esperando_15min(self):
        espelho.WEBHOOK_QUEUE = self.queue
        env = espelho.esperando_acima_de(15)
        self.assertEqual(env.state, MetricState.OK)
        assert isinstance(env.value, dict)
        self.assertEqual(env.value["n"], 1)
        self.assertEqual(env.value["lista"][0]["phone_final"], "final 2222")

    def test_atendidos(self):
        espelho.WEBHOOK_QUEUE = self.queue
        env = espelho.atendidos_hoje()
        self.assertEqual(env.state, MetricState.OK)
        self.assertEqual(env.value, 1)  # só c1 teve outbound

    def test_clientes_min(self):
        espelho.WEBHOOK_QUEUE = self.queue
        env = espelho.clientes_por_minuto(600)
        self.assertEqual(env.state, MetricState.OK)
        self.assertIsInstance(env.value, float)

    def test_telefone_final(self):
        self.assertEqual(telefone_final("557799991234"), "final 1234")


class TestGestorNeverZero(unittest.TestCase):
    def test_extrair_unavailable(self):
        env = MetricEnvelope.unavailable(
            "sem bearer",
            last_value={"faturamento": 99.0, "renovacoes": 3},
            source=SourceRef(id="gestor", label="Gestor", last_update="2026-10-05T12:00:00-03:00"),
            metric_id="inicio.kpis_gestor",
        )
        fat = extrair_kpi(env, "faturamento")
        self.assertEqual(fat.state, MetricState.UNAVAILABLE)
        self.assertEqual(fat.value, 99.0)
        self.assertNotEqual(fat.value, 0)

    def test_extrair_missing_key_not_zero(self):
        env = MetricEnvelope.ok(
            {"renovacoes": 5},
            metric_id="inicio.kpis_gestor",
            source=SourceRef(id="gestor", label="Gestor", last_update="x"),
        )
        fat = extrair_kpi(env, "faturamento")
        self.assertEqual(fat.state, MetricState.UNAVAILABLE)
        self.assertIsNone(fat.value)


class TestSeedGate(unittest.TestCase):
    def test_seed_off_by_default(self):
        with mock.patch.dict(os.environ, {"PAINEL_V2_SEED": "0"}, clear=False):
            self.assertFalse(seed.seed_habilitado())

    def test_seed_on(self):
        with mock.patch.dict(os.environ, {"PAINEL_V2_SEED": "1"}, clear=False):
            self.assertTrue(seed.seed_habilitado())
            s = seed.seed_inicio()
            self.assertTrue(s["is_seed"])
            self.assertIn("faturamento", s["kpis"])

    def test_montar_inicio_seed(self):
        async def _run():
            with mock.patch.dict(os.environ, {"PAINEL_V2_SEED": "1"}, clear=False):
                return await inicio_svc.montar_inicio({"periodo": "hoje"})

        import asyncio

        out = asyncio.run(_run())
        self.assertTrue(out["ok"])
        self.assertTrue(out["is_seed"])
        self.assertEqual(out["phase"], "F2")
        self.assertEqual(out["kpis"]["faturamento"]["state"], "ok")


class TestDrillInicio(unittest.TestCase):
    def test_drill_seed(self):
        with mock.patch.dict(os.environ, {"PAINEL_V2_SEED": "1"}, clear=False):
            payload = inicio_svc.drill_inicio("inicio.esperando_15min", 1, 10)
            self.assertGreaterEqual(payload["total"], 1)
            self.assertTrue(payload["rows"])


if __name__ == "__main__":
    unittest.main()
