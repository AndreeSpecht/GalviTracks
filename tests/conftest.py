import pytest
import requests
from werkzeug.security import generate_password_hash

from radar_tracker import auth, create_app
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
        SECRET_KEY = "chave-de-teste"
        ACESSO_PAINEL_INTERNET = False

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


# Hash barato nos testes (o scrypt padrão é lento de propósito)
SENHA_TESTE = "senha-teste"
HASH_TESTE = generate_password_hash(SENHA_TESTE, method="pbkdf2:sha256:1")


def criar_usuario(app, usuario="gestor", perfil="gestor", nome=None):
    return app.extensions["radar"]["banco"].criar_usuario(usuario, nome or usuario.title(), HASH_TESTE, perfil)


def entrar(cliente, uid):
    with cliente.session_transaction() as sessao:
        sessao["uid"] = uid
        sessao.permanent = True


@pytest.fixture(autouse=True)
def zerar_tentativas():
    auth._tentativas.clear()
    yield
    auth._tentativas.clear()


@pytest.fixture
def anonimo(app):
    """Cliente sem login."""
    return app.test_client()


@pytest.fixture
def client(app):
    """Cliente já logado como gestor (a maioria dos testes trata da API, não do login)."""
    cliente = app.test_client()
    entrar(cliente, criar_usuario(app))
    return cliente
