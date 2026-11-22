"""O modo --xmpp termina com erro quando a corrida não produz relatório."""

import os
import sys
import unittest
from unittest import mock

try:
    import spade
    from isia.simulation import runner
except ImportError:
    runner = None


@unittest.skipUnless(runner, "SPADE não está instalado")
class TestRunnerXmppExit(unittest.TestCase):
    def test_xmpp_run_without_report_exits_with_error(self):
        # Simula spade.run a engolir a falha de ligação: a corrotina nunca chega a imprimir.
        with mock.patch.object(sys, "argv", ["runner", "--xmpp"]), \
                mock.patch.dict(os.environ, {"XMPP_PASSWORD": "x"}), \
                mock.patch.object(spade, "run", side_effect=lambda coro: coro.close()):
            with self.assertRaises(SystemExit) as raised:
                runner.main()
        self.assertIn("Modo XMPP falhou", str(raised.exception.code))


if __name__ == "__main__":
    unittest.main()
