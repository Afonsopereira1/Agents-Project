"""Relógio manual em segundos simulados."""


class SimulationClock:
    """Relógio da simulação: começa em zero e só avança quando o simulador chama advance().

    Attributes:
        now (float): Instante atual, em segundos simulados (só leitura).
    """

    def __init__(self):
        """Iniciar o relógio em 0.0 segundos simulados."""
        self._now = 0.0

    @property
    def now(self) -> float:
        """Devolver o instante atual, usado em observações, mensagens e prazos da simulação.

        Returns:
            float: Segundos simulados desde o início.
        """
        return self._now

    def advance(self, seconds: float = 1.0) -> float:
        """Avançar por uma duração positiva; entradas inválidas não mudam o tempo.

        Args:
            seconds (float): Duração do avanço, em segundos simulados; finita e positiva.

        Returns:
            float: Novo instante atual.

        Raises:
            ValueError: Se ``seconds`` não for finito e positivo (``bool`` incluído) ou se o
                avanço exceder a capacidade ou a precisão do relógio.
        """
        if (
            isinstance(seconds, bool)
            or not isinstance(seconds, (int, float))
            or not 0 < seconds < float("inf")
        ):
            raise ValueError("O avanço deve ser finito e positivo, em segundos.")

        try:
            next_time = self._now + seconds
        except OverflowError as error:
            raise ValueError("O avanço excede a capacidade do relógio.") from error
        if not self._now < next_time < float("inf"):
            raise ValueError("O avanço excede a capacidade ou precisão do relógio.")

        self._now = next_time
        return self._now
