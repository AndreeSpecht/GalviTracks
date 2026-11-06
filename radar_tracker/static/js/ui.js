/* Componentes de interface: toasts, diálogos (com focus trap), confirmação e formulário. */
import { $, el } from './util.js';

// --- Toasts ---
const ICONE_TOAST = { sucesso: 'ok', erro: 'alerta', aviso: 'alerta', critico: 'semSinal', info: 'info' };

export function toast(mensagem, tipo = 'info', { titulo, duracao = 4500, acao } = {}) {
  const raiz = $('#toasts');
  const t = el('div', { className: `toast toast-${tipo}`, role: tipo === 'erro' || tipo === 'critico' ? 'alert' : 'status' },
    el('span', { className: 'toast-ic' }, { icone: ICONE_TOAST[tipo] || 'info' }),
    el('div', { className: 'toast-txt' }, titulo && el('strong', {}, titulo), el('span', {}, mensagem)),
    acao && el('button', { className: 'toast-acao', type: 'button', onclick: () => { acao.fn(); fechar(); } }, acao.rotulo),
    el('button', { className: 'toast-x', type: 'button', 'aria-label': 'Fechar aviso', onclick: () => fechar() }, { icone: 'x' }));
  raiz.append(t);
  requestAnimationFrame(() => t.classList.add('visivel'));
  let timer = setTimeout(fechar, duracao);
  t.addEventListener('mouseenter', () => clearTimeout(timer));
  t.addEventListener('mouseleave', () => { timer = setTimeout(fechar, 2000); });
  function fechar() {
    clearTimeout(timer);
    t.classList.remove('visivel');
    setTimeout(() => t.remove(), 250);
  }
  while (raiz.children.length > 4) raiz.firstElementChild.remove();
  return fechar;
}

export const erro = (e) => toast(e && e.message ? e.message : String(e), 'erro');

// --- Diálogos ---
const pilha = [];
let seq = 0;
const FOCAVEIS = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Abre um diálogo modal. Retorna { fechar(valor), caixa, corpo }.
 * aoFechar(valor) é chamado uma única vez (valor undefined quando fechado pelo X, Esc ou clique fora).
 */
export function dialogo({ titulo, subtitulo, corpo, rodape, tamanho = 'md', aoFechar, icone }) {
  const id = `dlg-${++seq}`;
  const anterior = document.activeElement;
  const corpoEl = el('div', { className: 'dlg-corpo' }, corpo);
  const caixa = el('div', { className: `dlg dlg-${tamanho}`, role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': id, tabindex: '-1' },
    el('header', { className: 'dlg-cab' },
      icone && el('span', { className: 'dlg-ic' }, { icone }),
      el('div', { className: 'dlg-titulos' }, el('h2', { id }, titulo), subtitulo && el('p', {}, subtitulo)),
      el('button', { className: 'btn-icone', type: 'button', 'aria-label': 'Fechar', onclick: () => fechar() }, { icone: 'x' })),
    corpoEl,
    rodape && el('footer', { className: 'dlg-rodape' }, rodape));
  const fundo = el('div', { className: 'dlg-fundo' }, caixa);
  fundo.addEventListener('mousedown', (e) => { if (e.target === fundo) fechar(); });
  caixa.addEventListener('keydown', (e) => {
    if (e.key !== 'Tab') return;
    const itens = [...caixa.querySelectorAll(FOCAVEIS)].filter((x) => x.offsetParent !== null);
    if (!itens.length) return;
    const [primeiro, ultimo] = [itens[0], itens[itens.length - 1]];
    if (e.shiftKey && document.activeElement === primeiro) { e.preventDefault(); ultimo.focus(); }
    else if (!e.shiftKey && document.activeElement === ultimo) { e.preventDefault(); primeiro.focus(); }
  });
  document.body.append(fundo);
  requestAnimationFrame(() => fundo.classList.add('aberto'));

  let fechado = false;
  function fechar(valor) {
    if (fechado) return;
    fechado = true;
    const i = pilha.indexOf(fechar);
    if (i >= 0) pilha.splice(i, 1);
    fundo.classList.remove('aberto');
    setTimeout(() => fundo.remove(), 200);
    if (anterior && anterior.focus) anterior.focus();
    if (aoFechar) aoFechar(valor);
  }
  pilha.push(fechar);
  setTimeout(() => {
    // Formulários e confirmações focam o campo/ação principal; janelas de consulta focam a própria caixa.
    const grande = tamanho === 'lg' || tamanho === 'xl';
    const alvo = caixa.querySelector('[autofocus]') || (grande ? caixa : caixa.querySelector('input, select, textarea') ||
      caixa.querySelector('.dlg-rodape .btn-primario') || caixa.querySelector(FOCAVEIS));
    if (alvo) alvo.focus({ preventScroll: true });
  }, 30);
  return { fechar, caixa, corpo: corpoEl };
}

/** Fecha o diálogo do topo. Retorna true se havia algum aberto. */
export function fecharDialogoTopo() {
  const f = pilha[pilha.length - 1];
  if (!f) return false;
  f();
  return true;
}

export const haDialogoAberto = () => pilha.length > 0;

export function confirmar(mensagem, { titulo = 'Confirmar', ok = 'Confirmar', perigo = false, icone = 'alerta' } = {}) {
  return new Promise((resolve) => {
    const d = dialogo({
      titulo,
      icone,
      tamanho: 'sm',
      corpo: el('p', { className: 'dlg-texto' }, mensagem),
      rodape: [
        el('button', { className: 'btn btn-sec', type: 'button', onclick: () => d.fechar(false) }, 'Cancelar'),
        el('button', { className: `btn ${perigo ? 'btn-perigo' : 'btn-primario'}`, type: 'button', onclick: () => d.fechar(true) }, ok),
      ],
      aoFechar: (v) => resolve(v === true),
    });
  });
}

/**
 * Formulário em diálogo. campos: [{ nome, rotulo, tipo='text', valor, obrigatorio, placeholder, dica }].
 * Resolve com { nome: valor } ou null se cancelado.
 */
export function formulario({ titulo, subtitulo, campos, ok = 'Salvar', icone }) {
  return new Promise((resolve) => {
    const entradas = {};
    const form = el('form', { className: 'form', novalidate: true },
      campos.map((c, i) => {
        const id = `campo-${seq}-${c.nome}`;
        const inp = el('input', {
          id, name: c.nome, type: c.tipo || 'text', value: c.valor ?? '', placeholder: c.placeholder,
          autocomplete: 'off', autofocus: i === 0 ? true : undefined, className: c.tipo === 'color' ? 'inp-cor' : 'inp',
        });
        entradas[c.nome] = inp;
        return el('label', { className: 'campo', for: id },
          el('span', { className: 'campo-rotulo' }, c.rotulo, c.obrigatorio ? el('em', {}, ' *') : null),
          inp,
          el('span', { className: 'campo-erro', 'aria-live': 'polite' }),
          c.dica && el('span', { className: 'campo-dica' }, c.dica));
      }),
      el('button', { type: 'submit', hidden: true }));
    form.addEventListener('submit', (e) => { e.preventDefault(); enviar(); });

    function enviar() {
      const valores = {};
      let valido = true;
      for (const c of campos) {
        const inp = entradas[c.nome];
        const v = inp.value.trim();
        const erroEl = inp.parentElement.querySelector('.campo-erro');
        erroEl.textContent = '';
        inp.removeAttribute('aria-invalid');
        if (c.obrigatorio && !v) {
          erroEl.textContent = 'Campo obrigatório.';
          inp.setAttribute('aria-invalid', 'true');
          if (valido) inp.focus();
          valido = false;
        }
        valores[c.nome] = v;
      }
      if (valido) d.fechar(valores);
    }

    const d = dialogo({
      titulo, subtitulo, icone, tamanho: 'sm', corpo: form,
      rodape: [
        el('button', { className: 'btn btn-sec', type: 'button', onclick: () => d.fechar(null) }, 'Cancelar'),
        el('button', { className: 'btn btn-primario', type: 'button', onclick: enviar }, ok),
      ],
      aoFechar: (v) => resolve(v && typeof v === 'object' ? v : null),
    });
  });
}

// --- Som de alerta (opcional, gerado na hora; sem arquivo de áudio) ---
let ctxAudio = null;
export function bipe() {
  try {
    ctxAudio ||= new (window.AudioContext || window.webkitAudioContext)();
    const t = ctxAudio.currentTime;
    [0, 0.18].forEach((d) => {
      const o = ctxAudio.createOscillator();
      const g = ctxAudio.createGain();
      o.type = 'sine';
      o.frequency.value = 880;
      g.gain.setValueAtTime(0.0001, t + d);
      g.gain.exponentialRampToValueAtTime(0.2, t + d + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, t + d + 0.15);
      o.connect(g).connect(ctxAudio.destination);
      o.start(t + d);
      o.stop(t + d + 0.16);
    });
  } catch { /* áudio indisponível */ }
}
