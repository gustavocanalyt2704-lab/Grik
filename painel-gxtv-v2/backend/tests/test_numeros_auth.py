"""Login próprio do v2 e métricas por número — sem número inventado."""

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

from app.core.states import MetricEnvelope  # noqa: E402
from app.services import numeros as numeros_svc  # noqa: E402
from app.sources import espelho  # noqa: E402


class TestLoginProprio(unittest.TestCase):
    def test_mesma_senha_do_v1_sem_ler_v1_no_login(self):
        import bcrypt

        from app.core import auth

        senha = "REDACTED"
        hashed = bcrypt.hashpw(senha.encode(), bcrypt.gensalt(rounds=4)).decode()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        v1 = Path(tmp.name) / "v1-auth.json"
        v2 = Path(tmp.name) / "v2-auth.json"
        v1.write_text(json.dumps({"usuario": "gustavo", "hash": hashed}), encoding="utf-8")
        env = {
            "PAINEL_V1_AUTH_FILE": str(v1),
            "PAINEL_V2_AUTH_FILE": str(v2),
            "PAINEL_PASSWORD": "",
            "PAINEL_V2_PASSWORD": "",
            "PAINEL_PASSWORD_SHA256": "",
            "PAINEL_V2_DEV_AUTH": "",
            "PAINEL_USER": "gustavo",
            "PAINEL_V2_SECURE_COOKIE": "0",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            self.assertTrue(auth.importar_credencial_v1())
            antes = v1.read_text(encoding="utf-8")
            v1.unlink()
            self.assertIsNone(auth.diagnosticar_login("gustavo", senha))
            self.assertIsNotNone(auth.diagnosticar_login("gustavo", "outra"))
            self.assertFalse(v1.exists())
            self.assertIn("importado_do_v1", v2.read_text(encoding="utf-8"))
            self.assertEqual(antes, json.dumps({"usuario": "gustavo", "hash": hashed}))

            from fastapi.testclient import TestClient
            from app.main import app

            espelho.WEBHOOK_QUEUE = Path(tmp.name) / "sem-fila.jsonl"
            with TestClient(app) as client:
                ruim = client.post(
                    "/api/v2/auth/login",
                    json={"username": "gustavo", "password": "outra"},
                )
                self.assertFalse(ruim.json()["ok"])
                ok = client.post(
                    "/api/v2/auth/login",
                    json={"username": "gustavo", "password": senha},
                )
                self.assertTrue(ok.json()["ok"], ok.json())
                me = client.get("/api/v2/auth/me")
                self.assertEqual(me.status_code, 200)
                self.assertEqual(me.json()["user"]["username"], "gustavo")
                inicio = client.get("/api/v2/inicio")
                self.assertEqual(inicio.status_code, 200)
                body = inicio.json()
                self.assertEqual(body["numeros"]["cards"], [])
                self.assertEqual(body["numeros"]["resumo"]["pagamentos"]["rotulo"], "sem dado")
                self.assertEqual(body["numeros"]["resumo"]["renovacoes"]["rotulo"], "sem dado")
                self.assertEqual(body["numeros"]["resumo"]["pediram_assinatura"]["rotulo"], "sem dado")


class TestNumerosReais(unittest.TestCase):
    def test_conta_so_o_que_a_fonte_traz(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        queue = Path(tmp.name) / "queue.jsonl"
        now = time.time()
        rows = [
            {
                "telefone": "557799991111",
                "conversa": "c1",
                "from_me": False,
                "text": "quero",
                "timestamp": now - 80,
                "instancia": "vendas-3619",
            },
            {
                "telefone": "557799991111",
                "conversa": "c1",
                "from_me": True,
                "text": "Fechado. Pra pagar é só o Pix 👇\nchave",
                "timestamp": now - 40,
                "instancia": "vendas-3619",
            },
            {
                "telefone": "557799992222",
                "conversa": "c2",
                "from_me": False,
                "text": "oi",
                "timestamp": now - 10,
                "instancia": "0837",
            },
            {
                "telefone": "557799993333",
                "conversa": "c3",
                "from_me": False,
                "text": "oi do 3166",
                "timestamp": now - 5,
                "instancia": "loja-3166",
            },
            {
                "telefone": "557799994444",
                "conversa": "c4",
                "from_me": False,
                "text": "quanto custa o plano",
                "timestamp": now - 30,
                "instancia": " 💙 COBRANÇA P2 💙 ",
            },
            {
                "telefone": "557799995555",
                "conversa": "c5",
                "from_me": False,
                "text": "não abre",
                "timestamp": now - 20,
                "instancia": "💙 P2 SUPORTE 💙",
            },
            {
                "telefone": "557799996666",
                "conversa": "c6",
                "from_me": False,
                "text": "voltei",
                "timestamp": now - 15,
                "instancia": "ALPHA TECH RMKT",
            },
            {
                "telefone": "557799997777",
                "conversa": "c7",
                "from_me": False,
                "text": "oi",
                "timestamp": now - 12,
                "instancia": "",
            },
            {
                "telefone": "557799993333",
                "conversa": "c8",
                "from_me": True,
                "text": "só o robô falou",
                "timestamp": now - 3,
                "instancia": "2884",
            },
        ]
        queue.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        gest = MetricEnvelope.ok(
            {
                "faturamento": 40,
                "renovacoes": 2,
                "vendas": [
                    {"telefone": "557799991111", "valor": 20, "instancia": "3619"},
                    {"telefone": "557700000999", "valor": 15},
                ],
            },
            metric_id="inicio.kpis_gestor",
        )
        env = {
            "WEBHOOK_QUEUE": str(queue),
            "ESPELHO_DIR": str(Path(tmp.name) / "sem-espelho"),
            "LIVE_LOG": str(Path(tmp.name) / "sem.log"),
            "PAINEL_V2_SEED": "0",
            "GESTOR_BEARER": "",
            "GESTOR_EMAIL": "",
            "GESTOR_PASSWORD": "",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            espelho.WEBHOOK_QUEUE = queue
            with mock.patch("app.services.numeros.credenciais.tem", return_value=True), mock.patch(
                "app.services.numeros.credenciais.aviso", return_value=None
            ):
                out = __import__("asyncio").run(numeros_svc.montar_numeros({"periodo": "hoje"}, gest=gest))
        por_vol = {c["id"]: c["conversas"]["valor"] for c in out["cards"]}
        ids = [c["id"] for c in out["cards"]]
        self.assertEqual(ids, sorted(ids, key=lambda i: (-por_vol[i], i.casefold())))
        self.assertCountEqual(
            ids,
            ["Final 3619", "Final 0837", "COBRANÇA P2", "Final 3166", "P2 SUPORTE", "ALPHA TECH RMKT", "sem número"],
        )
        self.assertNotIn("Final 2884", ids)
        por = {c["id"]: c for c in out["cards"]}
        self.assertEqual(por["Final 3619"]["grupo"], "vendas")
        self.assertEqual(por["Final 3619"]["conversas"]["valor"], 1)
        self.assertEqual(por["Final 3619"]["pix_enviados"]["valor"], 1)
        self.assertEqual(por["Final 3619"]["tempo_resposta"]["rotulo"], "40s")
        self.assertEqual(por["Final 3619"]["vendas_dia"]["valor"], 1)
        self.assertEqual(por["Final 0837"]["conversas"]["valor"], 1)
        self.assertEqual(por["Final 0837"]["pix_enviados"]["rotulo"], "sem dado")
        self.assertEqual(por["Final 0837"]["vendas_dia"]["valor"], 0)
        self.assertEqual(por["Final 3166"]["conversas"]["valor"], 1)
        self.assertEqual(por["COBRANÇA P2"]["grupo"], "cobranca")
        self.assertEqual(por["P2 SUPORTE"]["grupo"], "suporte")
        self.assertEqual(por["ALPHA TECH RMKT"]["grupo"], "rmkt")
        self.assertEqual(por["sem número"]["grupo"], "outros")
        self.assertEqual(out["resumo"]["pediram_assinatura"]["valor"], 1)
        titulos = [g["titulo"] for g in out["grupos"]]
        self.assertEqual(titulos, ["Vendas", "Cobrança", "Suporte", "RMKT", "Sem número"])
        origens = [v["origem"] for v in out["vendas"]]
        self.assertIn("Final 3619", origens)
        self.assertIn("origem não identificada", origens)

    def test_fila_magra_msg_3619(self):
        """A fila viva usa evento=msg_3619, não instancia=."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        queue = Path(tmp.name) / "queue.jsonl"
        now = time.time()
        rows = [
            {
                "received_at": time.strftime("%Y-%m-%dT%H:%M:%S-03:00", time.localtime(now - 30)),
                "payload": {
                    "evento": "msg_3619",
                    "telefone": "557799991111",
                    "conversa": "c-magra-3619",
                    "nome": "Ana",
                },
            },
            {
                "received_at": time.strftime("%Y-%m-%dT%H:%M:%S-03:00", time.localtime(now - 20)),
                "payload": {
                    "evento": "msg_0837",
                    "telefone": "557799992222",
                    "conversa": "c-magra-0837",
                    "nome": "Beto",
                },
            },
            {
                "received_at": time.strftime("%Y-%m-%dT%H:%M:%S-03:00", time.localtime(now - 10)),
                "evento": "msg_p6cob",
                "telefone": "557799993333",
                "conversa": "c-magra-p6",
                "nome": "P6",
            },
        ]
        queue.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        env = {
            "WEBHOOK_QUEUE": str(queue),
            "ESPELHO_DIR": str(Path(tmp.name) / "sem-espelho"),
            "LIVE_LOG": str(Path(tmp.name) / "sem.log"),
            "PAINEL_V2_SEED": "0",
            "GESTOR_BEARER": "",
            "GESTOR_EMAIL": "",
            "GESTOR_PASSWORD": "",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            espelho.WEBHOOK_QUEUE = queue
            out = __import__("asyncio").run(numeros_svc.montar_numeros({"periodo": "hoje"}))
        por = {c["id"]: c for c in out["cards"]}
        self.assertGreaterEqual(por["Final 3619"]["conversas"]["valor"], 1)
        self.assertNotEqual(por["Final 3619"]["conversas"]["rotulo"], "sem dado")
        self.assertGreaterEqual(por["Final 0837"]["conversas"]["valor"], 1)
        self.assertEqual(por["Final 3619"]["vendas_dia"]["rotulo"], "sem dado")
        self.assertEqual(por["COBRANÇA P6"]["grupo"], "cobranca")
        self.assertGreaterEqual(por["COBRANÇA P6"]["conversas"]["valor"], 1)

    def test_sem_fila_nao_inventa(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        env = {
            "WEBHOOK_QUEUE": str(Path(tmp.name) / "nao-existe.jsonl"),
            "PAINEL_V2_SEED": "0",
            "GESTOR_BEARER": "",
            "GESTOR_EMAIL": "",
            "GESTOR_PASSWORD": "",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            espelho.WEBHOOK_QUEUE = Path(tmp.name) / "nao-existe.jsonl"
            out = __import__("asyncio").run(numeros_svc.montar_numeros({"periodo": "hoje"}))
        self.assertIsNotNone(out["aviso_gestor"])
        self.assertEqual(out["cards"], [])
        self.assertEqual(out["resumo"]["pagamentos"]["rotulo"], "sem dado")
        self.assertEqual(out["resumo"]["renovacoes"]["rotulo"], "sem dado")
        self.assertNotEqual(out["resumo"]["pagamentos"]["valor"], 0)


class TestRotuloEResumo(unittest.TestCase):
    def test_nomes_do_grafico(self):
        casos = {
            "3619": ("Final 3619", "vendas"),
            "vendas-3619": ("Final 3619", "vendas"),
            "loja-3166": ("Final 3166", "vendas"),
            "0837": ("Final 0837", "vendas"),
            "1869": ("Final 1869", "vendas"),
            " 💙 COBRANÇA P2 💙 ": ("COBRANÇA P2", "cobranca"),
            "⚡⚠️ COBRANÇA P1 ⚠️⚡": ("COBRANÇA P1", "cobranca"),
            " 📺 COBRANÇA P6  📺": ("COBRANÇA P6", "cobranca"),
            "💙 P2 SUPORTE 💙": ("P2 SUPORTE", "suporte"),
            "💗 P4 SUPORTE💗 ": ("P4 SUPORTE", "suporte"),
            "📺SUPORTE P6📺": ("SUPORTE P6", "suporte"),
            "ALPHA TECH RMKT": ("ALPHA TECH RMKT", "rmkt"),
            "ALPHA TEC RMKT OFC": ("ALPHA TEC RMKT OFC", "rmkt"),
            "message sent": ("sem número", "outros"),
            "": ("sem número", "outros"),
            None: ("sem número", "outros"),
        }
        for bruto, (rotulo, grupo) in casos.items():
            self.assertEqual(numeros_svc.rotulo_instancia(bruto), rotulo, bruto)
            self.assertEqual(numeros_svc.grupo_de(rotulo), grupo, bruto)

    def test_pagamentos_reais_e_mp_sem_ok(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        queue = Path(tmp.name) / "queue.jsonl"
        agora = time.time()
        queue.write_text(
            json.dumps(
                {
                    "telefone": "557711110000",
                    "conversa": "c1",
                    "from_me": False,
                    "text": "oi",
                    "timestamp": agora - 20,
                    "instancia": "3619",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        contagem = Path(tmp.name) / "contagem.json"
        contagem.write_text(
            json.dumps(
                {
                    "hoje": {"mp_n": 19, "mp_reais": 726.9, "mp_ok": True, "renovado_n": 8, "renovado_reais": 240},
                    "ontem": {"mp_n": 4, "mp_reais": 80, "mp_ok": False, "renovado_n": 1, "renovado_reais": 30},
                }
            ),
            encoding="utf-8",
        )
        env = {
            "WEBHOOK_QUEUE": str(queue),
            "CONTAGEM_COMPLETA": str(contagem),
            "PAINEL_V2_SEED": "0",
            "GESTOR_BEARER": "",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            espelho.WEBHOOK_QUEUE = queue
            hoje = __import__("asyncio").run(numeros_svc.montar_numeros({"periodo": "hoje"}))
            ontem = __import__("asyncio").run(numeros_svc.montar_numeros({"periodo": "ontem"}))
            sete = __import__("asyncio").run(numeros_svc.montar_numeros({"periodo": "7d"}))
        self.assertEqual(hoje["resumo"]["pagamentos"]["rotulo"], "19")
        self.assertEqual(hoje["resumo"]["pagamentos"]["detalhe"], "R$ 726,90")
        self.assertEqual(hoje["resumo"]["renovacoes"]["rotulo"], "8")
        self.assertEqual(hoje["resumo"]["renovacoes"]["detalhe"], "R$ 240,00")
        self.assertEqual(hoje["cards"][0]["id"], "Final 3619")
        self.assertEqual(ontem["cards"], [])
        self.assertEqual(ontem["resumo"]["pagamentos"]["rotulo"], "sem dado")
        self.assertEqual(ontem["resumo"]["renovacoes"]["valor"], 1)
        self.assertEqual(sete["cards"][0]["id"], "Final 3619")
        self.assertEqual(sete["resumo"]["pagamentos"]["rotulo"], "sem dado")
        self.assertEqual(sete["resumo"]["renovacoes"]["rotulo"], "sem dado")

        so = __import__("asyncio").run(numeros_svc.montar_numeros({"periodo": "hoje", "numero": "3619"}))
        self.assertEqual([c["id"] for c in so["cards"]], ["Final 3619"])

    def test_contagem_do_cache_diario_do_painel_atual(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        pasta = Path(tmp.name) / "cache"
        pasta.mkdir()
        hoje = __import__("datetime").date.today().isoformat()
        (pasta / f"{hoje}.json").write_text(
            json.dumps(
                {
                    "gerado_em": "2026-10-06T11:46:52-03:00",
                    "bloco": {
                        "mp_ok": True,
                        "mp_n": 35,
                        "mp_reais": 1232.16,
                        "renovado_n": 26,
                        "renovado_reais": 1075.36,
                    },
                    "ontem_corte": {
                        "mp_ok": True,
                        "mp_n": 25,
                        "mp_reais": 822.56,
                        "renovado_n": 19,
                        "renovado_reais": 733.66,
                    },
                }
            ),
            encoding="utf-8",
        )
        queue = Path(tmp.name) / "queue.jsonl"
        queue.write_text("", encoding="utf-8")
        env = {
            "WEBHOOK_QUEUE": str(queue),
            "CONTAGEM_COMPLETA": "",
            "PAINEL_CONTADOR_CACHE": str(pasta),
            "PAINEL_V2_SEED": "0",
            "GESTOR_BEARER": "",
            "GESTOR_EMAIL": "",
            "GESTOR_PASSWORD": "",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            espelho.WEBHOOK_QUEUE = queue
            out = __import__("asyncio").run(numeros_svc.montar_numeros({"periodo": "hoje"}))
        self.assertEqual(out["resumo"]["pagamentos"]["rotulo"], "35")
        self.assertEqual(out["resumo"]["pagamentos"]["detalhe"], "R$ 1.232,16")
        self.assertEqual(out["resumo"]["renovacoes"]["rotulo"], "26")
        self.assertEqual(out["resumo"]["renovacoes"]["detalhe"], "R$ 1.075,36")

    def test_cobranca_p6_sem_nome_soma_na_mesma_linha(self):
        from app.core.mapa_instancias import invalidar_cache

        invalidar_cache()
        self.assertEqual(
            numeros_svc.rotulo_instancia("5511936235903"),
            "COBRANÇA P6",
        )
        self.assertEqual(
            numeros_svc.rotulo_instancia("", phone="11936235903"),
            "COBRANÇA P6",
        )
        self.assertEqual(
            numeros_svc.rotulo_instancia("message.sent", evento="msg_p6cob"),
            "COBRANÇA P6",
        )
        self.assertEqual(numeros_svc.grupo_de("COBRANÇA P6"), "cobranca")

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        queue = Path(tmp.name) / "queue.jsonl"
        now = time.time()
        rows = [
            {
                "timestamp": now - 40,
                "from_me": False,
                "text": "oi cobrador",
                "telefone": "557799990001",
                "conversa": "c-p6-nome",
                "instancia": " 📺 COBRANÇA P6  📺",
            },
            {
                "timestamp": now - 30,
                "from_me": False,
                "text": "quero renovar",
                "telefone": "557799990002",
                "conversa": "c-p6-tel",
                "instancia": "5511936235903",
            },
            {
                "timestamp": now - 20,
                "from_me": False,
                "text": "pix",
                "telefone": "557799990003",
                "conversa": "c-p6-evt",
                "evento": "msg_p6cob",
            },
            {
                "timestamp": now - 10,
                "from_me": False,
                "text": "oi vendas",
                "telefone": "5512981539217",
                "conversa": "c-sem-nome",
                "instancia": "message.sent",
            },
        ]
        queue.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        env = {
            "WEBHOOK_QUEUE": str(queue),
            "PAINEL_V2_SEED": "0",
            "GESTOR_BEARER": "",
            "GESTOR_EMAIL": "",
            "GESTOR_PASSWORD": "",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            espelho.WEBHOOK_QUEUE = queue
            out = __import__("asyncio").run(numeros_svc.montar_numeros({"periodo": "hoje"}))
        por = {c["id"]: c for c in out["cards"]}
        self.assertEqual(por["COBRANÇA P6"]["grupo"], "cobranca")
        self.assertEqual(por["COBRANÇA P6"]["conversas"]["valor"], 3)
        self.assertEqual(por["sem número"]["conversas"]["valor"], 1)
        self.assertNotIn("5511936235903", por)
        self.assertNotIn("Final 5903", por)
        cob = [g for g in out["grupos"] if g["id"] == "cobranca"]
        self.assertEqual(len(cob), 1)
        self.assertEqual([c["id"] for c in cob[0]["cards"]], ["COBRANÇA P6"])


if __name__ == "__main__":
    unittest.main()
