"""Validação de números usados nos cálculos do domínio."""

from math import isfinite


def is_finite_number(value: object) -> bool:
    """Aceita int/float finitos representáveis em float, excluindo booleanos."""
    if type(value) not in (int, float):
        return False
    try:
        return isfinite(value)
    except OverflowError:
        return False
