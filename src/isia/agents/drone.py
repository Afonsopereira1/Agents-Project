"""Drone: o ciclo comum de negociação e execução vive em mobile.py."""

from isia.agents.mobile import MobileResourceAgent


class DroneAgent(MobileResourceAgent):
    """Patrulha aérea; velocidade e consumo são definidos pelo cenário."""
