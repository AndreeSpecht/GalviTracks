# Imagem do GalviTracks para o servidor na nuvem (docs/nuvem.md).
# Funciona em x86 e ARM (Oracle Ampere): a imagem base do Python é multiarquitetura.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=America/Sao_Paulo

# Fuso horário de Brasília: datas do histórico, "hoje" e o backup das 3h dependem dele
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Usuário sem privilégios, com o mesmo uid do usuário padrão da VM (dono da pasta data/)
RUN useradd --uid 1000 --create-home galvitracks && mkdir -p /app/data && chown -R galvitracks /app/data
USER galvitracks

EXPOSE 5000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/api/health', timeout=4)"

CMD ["python", "run.py", "--no-browser", "--port", "5000"]
