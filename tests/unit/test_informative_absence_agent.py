"""Testar autorização semântica de ausência informativa no InformantAgent.

O funcionamento sem SPADE mantém-se coberto pelo teste do raciocínio puro.
"""
import unittest
from types import SimpleNamespace

from isia.communication.messages import Message, MessageType
from isia.domain.models import Position

try:
    import spade  # noqa: F401 - dependencia opcional nos testes
except ImportError:
    _informative_absence_payload = None
else:
    from isia.agents.informant import _informative_absence_payload


@unittest.skipUnless(_informative_absence_payload is not None, "SPADE nao instalado")
class TestInformativeAbsenceAgent(unittest.TestCase):
    def request(self, hypothesis=True):
        payload = {}
        if hypothesis:
            payload["hypothesis"] = {
                "hypothesis_id": "hypothesis-obs-0",
                "event_type": "gunshot_like_sound",
                "position": {"x": 5, "y": 5},
                "valid_from": 10.0,
                "valid_until": 12.0,
            }
        return Message("request-1", MessageType.VERIFY_REQUEST, 10.0, payload,
                       incident_id="incident-1", conversation_id="conv-1")

    def agent(self, **kwargs):
        data = {
            "coverage_position": Position(5, 5),
            "coverage_radius": 5.0,
            "coverage_capability": "acoustic",
            "coverage_observed_from": 9.0,
            "coverage_observed_until": 13.0,
            "coverage_opportunity_confirmed": True,
        }
        data.update(kwargs)
        return SimpleNamespace(**data)

    def test_modalidade_correta_e_cobertura_valida(self):
        result = _informative_absence_payload(self.agent(), self.request())
        self.assertTrue(result["declared_non_detection"])
        self.assertTrue(result["coverage"]["capability_validated"])

    def test_modalidade_inadequada_ou_desconhecida(self):
        for kind in ("visual", "other", None):
            with self.subTest(kind=kind):
                result = _informative_absence_payload(
                    self.agent(coverage_capability=kind), self.request()
                )
                self.assertIsNone(result)

    def test_fora_do_alcance(self):
        self.assertIsNone(_informative_absence_payload(
            self.agent(coverage_position=Position(30, 30)), self.request()
        ))

    def test_fora_da_janela_temporal(self):
        self.assertIsNone(_informative_absence_payload(
            self.agent(coverage_observed_from=11.0), self.request()
        ))
        self.assertIsNone(_informative_absence_payload(
            self.agent(coverage_observed_until=11.0), self.request()
        ))

    def test_ausencia_sem_oportunidade(self):
        self.assertIsNone(_informative_absence_payload(
            self.agent(coverage_opportunity_confirmed=False), self.request()
        ))

    def test_pedido_legado_sem_hipotese(self):
        self.assertIsNone(_informative_absence_payload(self.agent(), self.request(False)))


if __name__ == "__main__":
    unittest.main()
