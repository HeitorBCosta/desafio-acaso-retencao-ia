"""Intervalo de confiança da taxa de retorno (Wilson), o mesmo dos scripts de análise."""
import math

Z_95 = 1.959963984540054


def wilson(k: int, n: int, z: float = Z_95) -> tuple[float, float] | tuple[None, None]:
    """IC 95% de Wilson para k sucessos em n. Sem usuários, não há intervalo."""
    if n <= 0:
        return None, None
    if not 0 <= k <= n:
        raise ValueError(f"k={k} fora de [0, n={n}]")
    p = k / n
    centro = (p + z * z / (2 * n)) / (1 + z * z / n)
    margem = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centro - margem), min(1.0, centro + margem)
