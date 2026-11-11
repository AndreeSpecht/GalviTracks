import os

import pytest

from radar_tracker.config import carregar_arquivos_env

VAR = "GALVITRACKS_TESTE_ENV"


@pytest.fixture
def sem_var():
    os.environ.pop(VAR, None)
    yield
    os.environ.pop(VAR, None)


def test_env_local_tem_prioridade_sobre_env(tmp_path, sem_var):
    (tmp_path / ".env").write_text(f"{VAR}=do-env\n", encoding="utf-8")
    (tmp_path / ".env.local").write_text(f"{VAR}=do-env-local\n", encoding="utf-8")
    carregar_arquivos_env(tmp_path)
    assert os.environ[VAR] == "do-env-local"


def test_env_vale_sem_env_local(tmp_path, sem_var):
    (tmp_path / ".env").write_text(f"{VAR}=do-env\n", encoding="utf-8")
    carregar_arquivos_env(tmp_path)
    assert os.environ[VAR] == "do-env"


def test_variavel_de_ambiente_vence_os_arquivos(tmp_path, sem_var):
    os.environ[VAR] = "do-sistema"
    (tmp_path / ".env.local").write_text(f"{VAR}=do-env-local\n", encoding="utf-8")
    carregar_arquivos_env(tmp_path)
    assert os.environ[VAR] == "do-sistema"
