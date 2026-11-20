"""Guarda que aceita a tarefa respond_incident por Contract Net."""

from isia.agents.mobile import MobileResourceAgent


class RangerAgent(MobileResourceAgent):
    """Guarda que recebe intervenções; o runner dá-lhe a capacidade ``incident_response``."""
