"""Relógio manual em segundos simulados."""


class SimulationClock:
    """Começa em zero e avança apenas quando o simulador chama advance()."""

    def __init__(self):
        self._now = 0.0

    @property
    def now(self) -> float:
        """Instante para observações, mensagens e prazos da simulação."""
        return self._now

    def advance(self, seconds: float = 1.0) -> float:
        """Avança por uma duração positiva; entradas inválidas preservam o tempo."""
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
