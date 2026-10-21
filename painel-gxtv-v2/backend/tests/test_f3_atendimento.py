"""Testes F3 — funil + gaps de resposta (agrupa msgs seguidas)."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.atendimento import _response_gaps, _tempos_from_gaps, montar_atendimento, drill_atendimento


class TestResponseGaps(unittest.TestCase):
    def test_agrupa_msgs_seguidas(self):
        # cliente: t=0,10  (bloco) → resposta t=40 → gap = 30
        msgs = [
            {"from_me": False, "ts": 1000.0},
            {"from_me": False, "ts": 1010.0},
            {"from_me": True, "ts": 1040.0},
            {"from_me": True, "ts": 1045.0},  # mesmo bloco outbound
            {"from_me": False, "ts": 1100.0},
            {"from_me": True, "ts": 1120.0},
        ]
        gaps = _response_gaps(msgs)
        self.assertEqual(len(gaps), 2)
        self.assertEqual(gaps[0]["gap_s"], 30.0)
        self.assertEqual(gaps[1]["gap_s"], 20.0)

    def test_tempos(self):
        rows = [{"gap_s": x} for x in [10, 20, 30, 40, 100]]
        t = _tempos_from_gaps(rows)
        self.assertEqual(t["n"], 5)
        self.assertEqual(t["media"], 40.0)
        self.assertEqual(t["mediana"], 30)
        self.assertEqual(t["max"], 100)


class TestAtendimentoSeed(unittest.TestCase):
    def test_montar_seed(self):
        with mock.patch.dict(os.environ, {"PAINEL_V2_SEED": "1"}, clear=False):
            out = montar_atendimento({"periodo": "hoje"})
        self.assertTrue(out["ok"])
        self.assertEqual(out["phase"], "F3")
        self.assertEqual(out["funil"]["state"], "ok")
        stages = out["funil"]["value"]["stages"]
        labels = " ".join(s["label"] for s in stages).casefold()
        self.assertNotIn("abandonado", labels)
        self.assertEqual(out["tempos"]["media"]["state"], "ok")

    def test_drill_funil(self):
        with mock.patch.dict(os.environ, {"PAINEL_V2_SEED": "1"}, clear=False):
            d = drill_atendimento("atendimento.funil", 1, 10, stage="novo")
        self.assertGreaterEqual(d["total"], 1)


if __name__ == "__main__":
    unittest.main()
