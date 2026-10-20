"""Testes F4–F7 — comercial, operação, robô, relatório TG (dry)."""

from __future__ import annotations

import asyncio
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services import comercial as comercial_svc
from app.services import operacao as operacao_svc
from app.services import robo as robo_svc
from app.services.atendimento import _response_gaps


class TestComercialF4(unittest.TestCase):
    def test_seed(self):
        async def _run():
            with mock.patch.dict(os.environ, {"PAINEL_V2_SEED": "1"}, clear=False):
                return await comercial_svc.montar_comercial({"periodo": "hoje"})

        out = asyncio.run(_run())
        self.assertEqual(out["phase"], "F4")
        self.assertEqual(out["vendas"]["state"], "ok")
        items = (out["dist_whatsapp"]["value"] or {}).get("items") or []
        ids = {i["id"] for i in items}
        self.assertIn("3619", ids)
        self.assertIn("0837", ids)


class TestOperacaoF5(unittest.TestCase):
    def test_seed_sem_abandonado(self):
        with mock.patch.dict(os.environ, {"PAINEL_V2_SEED": "1"}, clear=False):
            out = operacao_svc.montar_operacao({"periodo": "hoje"})
        self.assertEqual(out["phase"], "F5")
        blob = str(out).casefold()
        self.assertNotIn("abandonado", blob)
        self.assertEqual(out["problemas"]["state"], "ok")
        self.assertIn("cruzamentos", out["correlacoes"]["value"])


class TestRoboF6(unittest.TestCase):
    def test_seed_tooltips(self):
        with mock.patch.dict(os.environ, {"PAINEL_V2_SEED": "1"}, clear=False):
            out = robo_svc.montar_robo({"periodo": "hoje"})
        self.assertEqual(out["phase"], "F6")
        self.assertTrue(out["catalogo"])
        self.assertIn("label_claro", out["ocupadas"]["value"])
        for m in out["catalogo"]:
            self.assertTrue(m["definition"])
            self.assertTrue(m["formula"])


class TestRelatorioF7(unittest.TestCase):
    def test_montar_texto_dry(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        # import as module path under backend
        import importlib.util

        path = ROOT / "scripts" / "relatorio_diario_tg.py"
        spec = importlib.util.spec_from_file_location("relatorio_diario_tg", path)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        with mock.patch.dict(os.environ, {"PAINEL_V2_SEED": "1"}, clear=False):
            spec.loader.exec_module(mod)
            texto = asyncio.run(mod.montar_texto())
        self.assertIn("MN Tecnologia", texto)
        self.assertNotIn("GXTV", texto)
        self.assertIn("America/Bahia", texto)
        self.assertIn("Faturamento", texto)
        self.assertNotIn("abandonado", texto.casefold())


class TestGapsStillOk(unittest.TestCase):
    def test_gap_basico(self):
        gaps = _response_gaps(
            [
                {"from_me": False, "ts": 1.0},
                {"from_me": True, "ts": 11.0},
            ]
        )
        self.assertEqual(gaps[0]["gap_s"], 10.0)


if __name__ == "__main__":
    unittest.main()
