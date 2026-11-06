"""SSE limitado por aplicação; espera por condição e agrupa mudanças rápidas."""

import json
import threading
import time


class Streams:
    def __init__(self, limite):
        self._vagas = threading.BoundedSemaphore(limite)

    def reservar(self):
        if not self._vagas.acquire(blocking=False):
            return None
        lock = threading.Lock()
        liberada = False

        def liberar():
            nonlocal liberada
            with lock:
                if not liberada:
                    liberada = True
                    self._vagas.release()

        return liberar


def eventos(frota, snapshot, liberar, desconectado=lambda: False, ping_s=15, intervalo_s=0.25):
    """snapshot(estado) enriquece o mesmo objeto usado pelo endpoint de polling.

    O callback não depende do contexto Flask, nem mantém uma conexão SQL aberta.
    O timeout também recalcula online/alertas sem precisar chegar outro GPS.
    """
    def evento(dados):
        return "event: estado\ndata: " + json.dumps(dados, ensure_ascii=False, allow_nan=False) + "\n\n"

    try:
        versao, anterior = frota.snapshot_com_versao(snapshot)
        ultimo = time.monotonic()
        yield "retry: 3000\n" + evento(anterior)
        while not frota.encerrada and not desconectado():
            nova = frota.esperar_mudanca(versao, ping_s)
            if frota.encerrada or desconectado():
                break
            mudou = nova != versao
            if mudou:
                frota.aguardar_intervalo(intervalo_s - (time.monotonic() - ultimo))
                if frota.encerrada:
                    break
            versao, atual = frota.snapshot_com_versao(snapshot)
            ultimo = time.monotonic()
            if mudou or atual != anterior:
                anterior = atual
                yield evento(atual)
            else:
                yield ": ping\n\n"
    finally:
        liberar()
