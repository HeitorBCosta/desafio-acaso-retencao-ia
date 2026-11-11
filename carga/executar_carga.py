"""
Roda a análise na ordem certa e carrega o resultado no PostgreSQL.

É o que o contêiner "carga" executa no docker compose, mas também funciona fora dele.
Se a base do Brasil ainda não existir em data/bronze, começa baixando o WildChat-1M
(cerca de 3,4 GB). Depois monta os campos da primeira conversa, calcula o desfecho, os
efeitos, as duas checagens de seleção e o tema, e grava tudo na base analítica.
Se uma etapa falhar, a carga para ali e o banco continua com a carga anterior.

Os scripts de exploração (02, 03, 05, 05b, 08, 10, 10b e 12) não entram aqui: eles
geraram relatórios e amostras usados nas decisões, mas o dashboard não depende deles.

Como rodar fora do Docker, a partir da raiz do projeto:
    $env:DATABASE_URL = "postgresql://acaso:acaso@localhost:5432/acaso"
    python carga/executar_carga.py
"""
import os
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
BRONZE = RAIZ / "data/bronze/wildchat_brazil.parquet"

ETAPAS = [
    "04_campos_primeira_conversa.py",
    "06_desfecho_retorno.py",
    "07_efeitos.py",
    "07b_recusa_motivo.py",
    "08b_temas_dicionario.py",
    "09_gpt4_selecao.py",
    "11_carregar_postgres.py",
]


def rodar(script: str) -> None:
    print(f"\n=== {script}", flush=True)
    inicio = time.monotonic()
    resultado = subprocess.run([sys.executable, f"scripts/{script}"], cwd=RAIZ)
    if resultado.returncode != 0:
        sys.exit(f"Carga interrompida: {script} terminou com erro ({resultado.returncode}).")
    print(f"=== {script}: {time.monotonic() - inicio:.0f} s", flush=True)


def main() -> None:
    if not BRONZE.exists() or os.environ.get("BAIXAR_DE_NOVO") == "1":
        rodar("01_baixar_wildchat.py")
    else:
        print(f"Base do Brasil já existe em {BRONZE.relative_to(RAIZ)}; download pulado.")
    for etapa in ETAPAS:
        rodar(etapa)
    print("\nCarga completa.")


if __name__ == "__main__":
    main()
