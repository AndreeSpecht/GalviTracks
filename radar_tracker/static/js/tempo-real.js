/*
 * Recebe o estado da frota.
 * - Servidor novo (motoboys trazem o campo `versao`): Server-Sent Events em /api/stream.
 * - Servidor atual ou stream indisponível: polling de /api/estado a cada 2 s
 *   (10 s com a aba oculta), voltando ao stream com backoff de 5 s, 10 s e 30 s.
 */
import { get } from './api.js';
import { app, emit } from './estado.js';

const POLL_MS = 2000;
const POLL_OCULTO_MS = 10000;
const BACKOFF_MS = [5000, 10000, 30000];

export function iniciarTempoReal() {
  let fonte = null;
  let timer = null;
  let emVoo = false;
  let pendente = false;
  let falhas = 0;

  const streamAberto = () => fonte && fonte.readyState === 1;

  function definirConexao(c) {
    if (app.conexao === c) return;
    app.conexao = c;
    emit('conexao', c);
  }

  function aplicar(estado) {
    if (!estado || typeof estado !== 'object') return;
    app.estado = estado;
    if (!app.backendNovo && Object.values(estado).some((m) => m && 'versao' in m)) {
      app.backendNovo = true;
      emit('backend-novo');
      conectarStream();
    }
    emit('estado', estado);
  }

  async function consultar() {
    timer = null;
    if (emVoo) { pendente = true; return; }
    emVoo = true;
    try {
      aplicar(await get('/api/estado'));
      if (!streamAberto()) definirConexao('polling');
    } catch {
      definirConexao('offline');
    } finally {
      emVoo = false;
    }
    if (pendente) { pendente = false; consultar(); return; }
    if (!streamAberto()) agendar();
  }

  function agendar() {
    clearTimeout(timer);
    timer = setTimeout(consultar, document.hidden ? POLL_OCULTO_MS : POLL_MS);
  }

  function conectarStream() {
    if (!window.EventSource || fonte) return;
    fonte = new EventSource('/api/stream');
    fonte.addEventListener('estado', (ev) => {
      falhas = 0;
      clearTimeout(timer);
      timer = null;
      definirConexao('ao-vivo');
      try { aplicar(JSON.parse(ev.data)); } catch { /* evento malformado: ignora */ }
    });
    fonte.onerror = () => {
      fonte.close();
      fonte = null;
      if (app.conexao === 'ao-vivo') definirConexao('polling');
      agendar();
      setTimeout(conectarStream, BACKOFF_MS[Math.min(falhas++, BACKOFF_MS.length - 1)]);
    };
  }

  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && !streamAberto()) consultar();
    emit('visibilidade', !document.hidden);
  });

  consultar();

  return {
    /** Força uma atualização imediata após uma ação do operador (no stream ela chega sozinha). */
    atualizarAgora() { if (!streamAberto()) consultar(); },
  };
}
