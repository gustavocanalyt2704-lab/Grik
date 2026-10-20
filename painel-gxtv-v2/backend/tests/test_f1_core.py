"""Testes F1 — timezone, registro, estados, telefone, gestor unavailable."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.metrics_registry import REGISTRY, get_metric, list_metrics, registry_payload
from app.core.states import MetricEnvelope, MetricState, gestor_indisponivel
from app.core.timezone import TZ_NAME, janela_periodo, telefone_final


class TestTimezone(unittest.TestCase):
    def test_tz_name(self):
        self.assertEqual(TZ_NAME, "America/Bahia")

    def test_janela_hoje(self):
        ini, fim, label = janela_periodo("hoje")
        self.assertEqual(ini.tzinfo.key, "America/Bahia")  # type: ignore[union-attr]
        self.assertLess(ini, fim)
        self.assertTrue(label)

    def test_telefone_final(self):
        self.assertEqual(telefone_final("557799991234"), "final 1234")
        self.assertEqual(telefone_final(None), "final —")


class TestRegistry(unittest.TestCase):
    def test_minimo_metricas(self):
        self.assertGreaterEqual(len(REGISTRY), 15)

    def test_campos_obrigatorios(self):
        for m in list_metrics():
            self.assertTrue(m.name)
            self.assertTrue(m.definition)
            self.assertTrue(m.source)
            self.assertTrue(m.formula)
            self.assertEqual(m.timezone, "America/Bahia")

    def test_sem_abandonado(self):
        blob = str(registry_payload()).casefold()
        self.assertNotIn("abandonado", blob)

    def test_gestor_vendas(self):
        m = get_metric("comercial.vendas")
        assert m is not None
        self.assertIn("gestor-iptv", m.source.casefold())


class TestStates(unittest.TestCase):
    def test_unavailable_preserva_valor(self):
        env = gestor_indisponivel({"vendas": 42}, "2026-10-05T12:00:00-03:00")
        self.assertEqual(env.state, MetricState.UNAVAILABLE)
        self.assertEqual(env.value, {"vendas": 42})
        self.assertIsNotNone(env.source)
        self.assertEqual(env.source.last_update, "2026-10-05T12:00:00-03:00")

    def test_ok_seed_flag(self):
        env = MetricEnvelope.ok(1, metric_id="x", is_seed=True)
        self.assertTrue(env.is_seed)


if __name__ == "__main__":
    unittest.main()
