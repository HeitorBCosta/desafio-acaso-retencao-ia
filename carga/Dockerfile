FROM python:3.14-slim

WORKDIR /app
COPY requirements-carga.txt .
RUN pip install --no-cache-dir -r requirements-carga.txt

# Só o que a carga usa. A pasta data/ não entra na imagem: vem montada do computador
# (docker-compose.yml), para o download de 3,4 GB acontecer uma vez só.
COPY scripts/ scripts/
COPY carga/ carga/
COPY db/ db/
COPY docs/rotulos/ docs/rotulos/

CMD ["python", "carga/executar_carga.py"]
