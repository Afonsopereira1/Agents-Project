"""Movimento base na grelha, primeiro em x e depois em y, sem obstáculos."""

from dataclasses import replace
from math import floor, isfinite, isclose

from isia.domain.models import MissionStatus, Position, ResourceStatus


def nonnegative(value: float, name: str) -> None:
    try:
        valid = type(value) in (int, float) and value >= 0 and isfinite(value)
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(f"{name} deve ser finito e não negativo.")


def position_at(origin: Position, target: Position, speed: float, elapsed: float) -> Position:
    """Células completas percorridas; não ultrapassa o destino nem perde frações."""
    if not isinstance(origin, Position) or not isinstance(target, Position):
        raise TypeError("A origem e o destino devem ser Position.")
    nonnegative(speed, "speed")
    nonnegative(elapsed, "elapsed")
    dx, dy = target.x - origin.x, target.y - origin.y
    distance = abs(dx) + abs(dy)
    if speed == 0 or elapsed == 0 or distance == 0:
        return origin
    # Limitar antes de multiplicar também evita overflow em durações grandes.
    steps = distance if elapsed >= distance / speed else floor(speed * elapsed)
    x_steps = min(steps, abs(dx))
    y_steps = min(steps - x_steps, abs(dy))
    return Position(origin.x + (x_steps if dx >= 0 else -x_steps),
                    origin.y + (y_steps if dy >= 0 else -y_steps))


# ponytail: grelha sem obstáculos; usar pesquisa de caminhos quando o mapa os incluir.
def distance(origin: Position, target: Position) -> int:
    return abs(origin.x - target.x) + abs(origin.y - target.y)


class MissionExecution:
    """Uma reserva, uma trajetória e um resultado, em segundos simulados.

    O inspetor recebe apenas a célula, o instante e a tarefa. Não se infere
    confirmação a partir da ausência de observações.
    """

    def __init__(self, reservation, mission, world, *, now, speed=1.0,
                 energy_per_cell=1.0, service_seconds=1.0, minimum_energy=0.0,
                 inspect):
        for name, value in (("now", now), ("speed", speed),
                            ("energy_per_cell", energy_per_cell),
                            ("service_seconds", service_seconds),
                            ("minimum_energy", minimum_energy)):
            nonnegative(value, name)
        if speed == 0 or not callable(inspect):
            raise ValueError("A execução exige velocidade positiva e um inspetor.")
        state = reservation.resource_state
        if reservation.reserved_mission_id != mission.mission_id or state.status is not ResourceStatus.RESERVED:
            raise ValueError("A missão precisa de uma reserva local confirmada.")
        self.reservation, self.world = reservation, world
        self.mission = replace(mission, status=MissionStatus.RESERVED).change_status(MissionStatus.RUNNING)
        self.home = state.position
        self.speed, self.energy_per_cell = speed, energy_per_cell
        self.service_seconds, self.minimum_energy = service_seconds, minimum_energy
        self.inspect = inspect
        self.now = self.phase_at = now
        self.origin = state.position
        self.result = None
        self.finished = False
        self.timeline = []
        self._record("reserved", now)
        self._state(state.change_status(ResourceStatus.MOVING), now)
        try:
            world.validate_position(self.home)
            world.validate_position(mission.target)
            cost = 2 * distance(self.home, mission.target) * energy_per_cell
            if state.autonomy_percent is None or (state.autonomy_percent < cost + minimum_energy and not isclose(
                    state.autonomy_percent, cost + minimum_energy, rel_tol=0, abs_tol=1e-10)):
                raise ValueError("autonomy_insufficient")
        except ValueError as error:
            self.interrupt(str(error))

    @property
    def resource(self):
        return self.reservation.resource_state

    def _record(self, event, at, **details):
        self.timeline.append({"time": at, "event": event,
                              "resource_id": self.resource.resource_id,
                              "mission_id": self.mission.mission_id,
                              "position": {"x": self.resource.position.x, "y": self.resource.position.y},
                              "energy": self.resource.autonomy_percent, **details})

    def _state(self, state, at, *, release=False):
        self.reservation.update_execution(self.mission.mission_id, state, release=release)
        self._record(state.status.value, at)
        self.finished = release

    def _result(self, outcome, reason, at):
        if self.result is None:
            self.result = {"outcome": outcome, "reason": reason, "completed_at": at}
            self.mission = self.mission.change_status(
                MissionStatus.FAILED if outcome == "failed" else MissionStatus.DONE)
            self._record("MISSION_RESULT", at, outcome=outcome, reason=reason)

    def interrupt(self, reason="mission_interrupted"):
        """Interromper no último instante avançado; regressar ou imobilizar."""
        if self.finished:
            return
        self._result("failed", reason, self.now)
        state = self.resource
        energy = state.autonomy_percent
        if energy is None or (energy < distance(state.position, self.home) * self.energy_per_cell and not isclose(
                energy, distance(state.position, self.home) * self.energy_per_cell, rel_tol=0, abs_tol=1e-10)):
            self._state(state.change_status(ResourceStatus.UNAVAILABLE), self.now, release=True)
            return
        if state.status is not ResourceStatus.RETURNING:
            self._state(state.change_status(ResourceStatus.RETURNING), self.now)
        self.origin, self.phase_at = state.position, self.now
        self.advance(self.now)

    def advance(self, now):
        nonnegative(now, "now")
        if now < self.now:
            raise ValueError("O relógio da missão não pode recuar.")
        self.now = now
        while not self.finished:
            state = self.resource
            if state.status is ResourceStatus.VERIFYING:
                completed_at = self.phase_at + self.service_seconds
                if now < completed_at:
                    return
                try:
                    outcome = self.inspect(state.position, completed_at, self.mission.task)
                    if outcome not in ("confirmed", "not_confirmed", "inconclusive", "failed"):
                        raise ValueError("invalid_inspection_result")
                    self._result(outcome, "local_inspection", completed_at)
                except Exception as error:
                    self._result("failed", f"inspection_error:{type(error).__name__}", completed_at)
                self.origin, self.phase_at = state.position, completed_at
                self._state(state.change_status(ResourceStatus.RETURNING), completed_at)
                continue
            target = self.home if state.status is ResourceStatus.RETURNING else self.mission.target
            destination = position_at(self.origin, target, self.speed, now - self.phase_at)
            self.world.validate_position(destination)
            cost = distance(state.position, destination) * self.energy_per_cell
            if state.autonomy_percent is None or (cost > state.autonomy_percent and not isclose(cost, state.autonomy_percent, rel_tol=0, abs_tol=1e-10)):
                self._result("failed", "energy_exhausted", now)
                self._state(state.change_status(ResourceStatus.UNAVAILABLE), now, release=True)
                return
            if destination != state.position:
                state = replace(state, position=destination, autonomy_percent=max(0.0, state.autonomy_percent - cost))
                self.reservation.update_execution(self.mission.mission_id, state)
                self._record("position", min(now, self.phase_at + distance(self.origin, target) / self.speed))
            if destination != target:
                return
            arrival = self.phase_at + distance(self.origin, target) / self.speed
            if state.status is ResourceStatus.RETURNING:
                self._state(state.change_status(ResourceStatus.AVAILABLE), arrival, release=True)
            else:
                self.phase_at = arrival
                self._state(state.change_status(ResourceStatus.VERIFYING), arrival)
