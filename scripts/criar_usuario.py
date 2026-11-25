"""Cria um usuário do painel ou define uma senha nova (útil no servidor, sem navegador).

Uso:
    python scripts/criar_usuario.py maria --nome "Maria Souza"              # operador
    python scripts/criar_usuario.py andre --nome "André" --perfil gestor
    python scripts/criar_usuario.py maria --redefinir                       # senha nova
    python scripts/criar_usuario.py --listar

A senha é pedida no terminal (sem aparecer). Para automatizar, use --senha-stdin:
    echo "senha-forte" | python scripts/criar_usuario.py maria --nome Maria --senha-stdin
"""

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from werkzeug.security import generate_password_hash  # noqa: E402

from radar_tracker.config import Config  # noqa: E402
from radar_tracker.db import Banco  # noqa: E402

PERFIS = ("operador", "gestor")
SENHA_MIN = 6


def ler_senha(da_entrada):
    if da_entrada:
        return sys.stdin.readline().rstrip("\r\n")
    senha = getpass.getpass("Senha: ")
    if senha != getpass.getpass("Confirme a senha: "):
        sys.exit("As senhas não conferem.")
    return senha


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("usuario", nargs="?", help="login (sem espaços)")
    parser.add_argument("--nome", help="nome que aparece no painel (padrão: o próprio login)")
    parser.add_argument("--perfil", choices=PERFIS, default="operador")
    parser.add_argument("--redefinir", action="store_true", help="define uma senha nova para um usuário existente")
    parser.add_argument("--listar", action="store_true", help="lista os usuários ativos")
    parser.add_argument("--senha-stdin", action="store_true", help="lê a senha da entrada padrão")
    args = parser.parse_args()

    Config.PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    banco = Banco(Config.DB_PATH)
    banco.inicializar()
    try:
        if args.listar:
            for u in banco.listar_usuarios():
                print(f"{u['usuario']:<20} {u['perfil']:<9} {u['nome']}")
            return
        if not args.usuario or " " in args.usuario:
            parser.error("informe o login do usuário, sem espaços")

        senha = ler_senha(args.senha_stdin)
        if len(senha) < SENHA_MIN:
            sys.exit(f"A senha precisa ter pelo menos {SENHA_MIN} caracteres.")

        if args.redefinir:
            registro = banco.usuario_para_login(args.usuario)
            if not registro or not registro["ativo"] or not banco.definir_senha(registro["id"], generate_password_hash(senha)):
                sys.exit(f"Usuário {args.usuario!r} não encontrado.")
            print(f"Senha de {args.usuario} redefinida.")
            return
        try:
            banco.criar_usuario(args.usuario, args.nome or args.usuario, generate_password_hash(senha), args.perfil)
        except ValueError as e:
            sys.exit(str(e))
        print(f"Usuário {args.usuario} ({args.perfil}) criado em {Config.DB_PATH}.")
    finally:
        banco.fechar()


if __name__ == "__main__":
    main()
