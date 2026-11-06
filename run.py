"""Ponto de entrada: python run.py [--debug] [--no-browser]"""

import argparse
import threading
import webbrowser

from radar_tracker import create_app
from radar_tracker.config import Config


def criar_servidor(app, port):
    """Configuração compartilhada com a verificação real do stream."""
    from waitress import create_server

    cfg = app.extensions["radar"]["config"]
    # clear_untrusted_proxy_headers=False: o waitress apagaria o X-Forwarded-For que o túnel
    # acrescenta, e é por ele que a API reconhece (e bloqueia) quem chega pela internet.
    return create_server(app, host=cfg.HOST, port=port, threads=cfg.THREADS,
                         send_bytes=1, channel_timeout=120, channel_request_lookahead=1,
                         clear_untrusted_proxy_headers=False)


def main():
    parser = argparse.ArgumentParser(description="Servidor do sistema de rastreamento de motoboys.")
    parser.add_argument("--debug", action="store_true", help="modo de desenvolvimento do Flask (recarga automática)")
    parser.add_argument("--no-browser", action="store_true", help="não abrir o navegador ao iniciar")
    parser.add_argument("--port", type=int, default=Config.PORT)
    args = parser.parse_args()

    app = create_app()
    url = f"http://127.0.0.1:{args.port}"
    if not args.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    print(f"Painel disponível em {url}  (Ctrl+C para encerrar)")

    servidor = None
    try:
        if args.debug:
            app.run(host=Config.HOST, port=args.port, debug=True, use_reloader=False, threaded=True)
        else:
            servidor = criar_servidor(app, args.port)
            servidor.run()
    finally:
        app.extensions["radar"]["frota"].fechar()  # acorda os geradores antes de esperar as threads HTTP
        if servidor is not None:
            servidor.close()
            servidor.task_dispatcher.shutdown()
        app.extensions["radar"]["fechar"]()


if __name__ == "__main__":
    main()
