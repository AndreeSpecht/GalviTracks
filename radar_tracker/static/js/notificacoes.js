/* Central de alertas (sino no topo), toasts para alertas novos e som opcional. */
import { emit, todosAlertas } from './estado.js';
import { icone } from './icones.js';
import { NOME_ICONE_ALERTA } from './painel.js';
import { $, el, gravarPref, lerPref, primeiroNome } from './util.js';
import { bipe, toast } from './ui.js';

let primeiraLeitura = true;
let conhecidos = new Set();
let somLigado = lerPref('som') === '1';

const btn = () => $('#btn-alertas');
const painel = () => $('#notif-painel');

export function montarNotificacoes() {
  btn().innerHTML = `${icone('sino')}<span class="badge" hidden></span>`;
  btn().addEventListener('click', (e) => { e.stopPropagation(); alternar(); });
  document.addEventListener('mousedown', (e) => {
    if (!painel().hidden && !e.target.closest('.notif')) fechar();
  });
}

export function aberto() { return !painel().hidden; }

function alternar() { if (aberto()) fechar(); else abrir(); }

function abrir() {
  painel().hidden = false;
  btn().setAttribute('aria-expanded', 'true');
  render();
}

export function fechar() {
  painel().hidden = true;
  btn().setAttribute('aria-expanded', 'false');
}

function render() {
  const lista = todosAlertas();
  const botaoSom = el('button', {
    className: 'btn-icone', type: 'button', 'aria-pressed': String(somLigado),
    title: somLigado ? 'Som ligado para alertas críticos' : 'Som desligado', 'aria-label': 'Som dos alertas',
    onclick: () => { somLigado = !somLigado; gravarPref('som', somLigado ? '1' : '0'); if (somLigado) bipe(); render(); },
  }, { icone: somLigado ? 'somLigado' : 'somDesligado' });
  painel().replaceChildren(
    el('div', { className: 'notif-cab' }, el('strong', {}, 'Alertas'), el('span', { className: 'contador' }, String(lista.length)), botaoSom),
    lista.length
      ? el('ul', { className: 'notif-lista' }, ...lista.map((a) => el('li', {},
        el('button', { className: `notif-item nivel-${a.nivel}`, type: 'button', onclick: () => { fechar(); emit('selecionar-moto', a.mid); emit('centralizar-moto', a.mid); } },
          el('span', { className: 'notif-ic' }, { icone: NOME_ICONE_ALERTA[a.tipo] || 'alerta' }),
          el('span', { className: 'notif-txt' }, el('strong', {}, a.m.nome), el('span', {}, a.mensagem)),
          el('span', { className: 'notif-ver' }, 'Ver')))))
      : el('div', { className: 'notif-vazio' }, el('span', { className: 'vazio-ic-wrap ok' }, { icone: 'ok' }), el('strong', {}, 'Tudo certo com a frota'), el('span', {}, 'Nenhum alerta ativo agora.')));
}

export function atualizarNotificacoes() {
  const lista = todosAlertas();
  const b = btn().querySelector('.badge');
  b.hidden = !lista.length;
  b.textContent = lista.length > 9 ? '9+' : String(lista.length);
  const pior = lista.length ? lista[0].nivel : '';
  b.className = `badge ${pior ? `badge-${pior}` : ''}`;
  btn().classList.toggle('tem-critico', pior === 'critico');
  btn().setAttribute('aria-label', lista.length ? `Alertas: ${lista.length} ativo(s)` : 'Alertas: nenhum');

  // Toast para alertas críticos/de parada que acabaram de surgir
  const agora = new Set(lista.map((a) => `${a.mid}:${a.tipo}`));
  if (!primeiraLeitura) {
    for (const a of lista) {
      const chave = `${a.mid}:${a.tipo}`;
      if (conhecidos.has(chave) || a.nivel === 'aviso') continue;
      toast(a.mensagem, a.nivel === 'critico' ? 'critico' : 'aviso', {
        titulo: primeiroNome(a.m.nome),
        duracao: 8000,
        acao: { rotulo: 'Ver', fn: () => { emit('selecionar-moto', a.mid); emit('centralizar-moto', a.mid); } },
      });
      if (somLigado && a.nivel === 'critico') bipe();
    }
  }
  conhecidos = agora;
  primeiraLeitura = false;
  if (aberto()) render();
}

