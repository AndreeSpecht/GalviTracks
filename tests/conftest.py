import pytest
import requests

from radar_tracker import create_app
from radar_tracker.config import Config
from radar_tracker.frota import Frota

MOTOBOYS = [
    {"id": 0, "nome": "Ana Teste", "cor": "#e74c3c", "tid": "0"},
    {"id": 1, "nome": "Bruno Teste", "cor": "#3498db", "tid": "b1"},
]


@pytest.fixture
def cfg(tmp_path):
    class ConfigTeste(Config):
        PASTA_DADOS = tmp_path
        DB_PATH = tmp_path / "teste.db"
        ARQUIVO_SESSAO = tmp_path / "sessao.json"
        OWNTRACKS_TOKEN = ""
        NGROK_DOMAIN = ""

    return ConfigTeste


@pytest.fixture(autouse=True)
def sem_rede(monkeypatch):
    """Nenhum teste acessa OSRM/Nominatim de verdade: simula serviço fora do ar."""

    def falhar(*_args, **_kwargs):
        raise requests.ConnectionError("rede desabilitada nos testes")

    monkeypatch.setattr(requests, "get", falhar)


@pytest.fixture
def app(cfg):
    app = create_app(cfg, motoboys=[dict(m) for m in MOTOBOYS])
    yield app
    app.extensions["radar"]["fechar"]()


@pytest.fixture(autouse=True)
def fechar_frotas(monkeypatch):
    """Encerra também as frotas criadas diretamente pelos testes de domínio."""
    instancias = []
    original = Frota.__init__

    def iniciar(self, *args, **kwargs):
        original(self, *args, **kwargs)
        instancias.append(self)

    monkeypatch.setattr(Frota, "__init__", iniciar)
    yield
    for frota in instancias:
        frota.fechar()


@pytest.fixture
def client(app):
    return app.test_client()
