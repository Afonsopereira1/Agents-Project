"""Validação de números usados nos cálculos do domínio."""

from math import isfinite


def is_finite_number(value: object) -> bool:
    """Aceitar int/float finitos e representáveis em float, excluindo booleanos.

    Args:
        value (object): Valor a verificar.

    Returns:
        bool: ``True`` se o tipo for exatamente ``int`` ou ``float`` e o valor for finito.
    """
    if type(value) not in (int, float):
        return False
    try:
        return isfinite(value)
    except OverflowError:
        return False
