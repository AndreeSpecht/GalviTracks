/* Painel de rastreamento de motoboys — Galvitech Ltda. Ponto de entrada (módulo ES). */
import { get } from './api.js';
import { app, carregarClientes, emit, on, selecionar } from './estado.js';
import { icone } from './icones.js';
import { aplicarTemaMapa, enquadrar, map } from './mapa.js';
import { atualizarMarcadores, posicaoExibida, realcarSelecao, sincronizarAnimacoes, todasPosicoes } from './marcadores.js';
import { desenharRota } from './rota.js';
import { abrirGestao, alternarVisibilidade, aoMudarClientes, emModoMira, entrarModoMira, sairModoMira } from './clientes.js';
import { adicionarParada, focarBusca, montarDetalhe, renderDetalhe, renderEstimativa, renderFrota } from './painel.js';
import { atualizarNotificacoes, aberto as notifAberta, fechar as fecharNotif, montarNotificacoes } from './notificacoes.js';
import { buscarResumo, renderResumo } from './resumo.js';
import { abrirHistorico } from './historico.js';
import { abrirReplay, fecharReplay, replayAberto } from './replay.js';
import { iniciarTempoReal } from './tempo-real.js';
import { $, digitando, el, gravarPref, lerPref, telaPequena } from './util.js';
import { erro, fecharDialogoTopo, haDialogoAberto } from './ui.js';

/* global L */

// --- Tema claro/escuro ---
const mqEscuro = window.matchMedia('(prefers-color-scheme: dark)');
function aplicarTema(tema) {
  document.documentElement.dataset.tema = tema;
  aplicarTemaMapa(tema);
  const btn = $('#btn-tema');
  btn.innerHTML = icone(tema === 'escuro' ? 'sol' : 'lua');
  btn.title = tema === 'escuro' ? 'Usar tema claro' : 'Usar tema escuro';
  document.querySelector('meta[name="theme-color"]').content = tema === 'escuro' ? '#0b1120' : '#ffffff';
}
$('#btn-tema').addEventListener('click', () => {
  const novo = document.documentElement.dataset.tema === 'escuro' ? 'claro' : 'escuro';
  gravarPref('tema', novo);
  aplicarTema(novo);
});
mqEscuro.addEventListener('change', (e) => { if (!lerPref('tema')) aplicarTema(e.matches ? 'escuro' : 'claro'); });
aplicarTema(document.documentElement.dataset.tema);

// --- Topo ---
$('#btn-historico').append(el('span', {}, { icone: 'historico' }), el('span', { className: 'rotulo' }, 'Histórico'));
$('#btn-historico').addEventListener('click', abrirHistorico);
$('#btn-clientes').append(el('span', {}, { icone: 'usuarios' }), el('span', { className: 'rotulo' }, 'Clientes'));
$('#btn-clientes').addEventListener('click', abrirGestao);
$('.marca-logo').innerHTML = icone('moto');

const btnPainel = $('#btn-painel');
btnPainel.innerHTML = icone('painel');
function definirPainelRecolhido(v) {
  document.body.classList.toggle('painel-recolhido', v);
  btnPainel.setAttribute('aria-pressed', String(!v));
  gravarPref('painel', v ? 'recolhido' : 'aberto');
  setTimeout(() => map.invalidateSize({ pan: false }), 260);
}
btnPainel.addEventListener('click', () => definirPainelRecolhido(!document.body.classList.contains('painel-recolhido')));
if (lerPref('painel') === 'recolhido') definirPainelRecolhido(true);

const ROTULO_CONEXAO = {
  conectando: ['Conectando…', 'Conectando ao servidor'],
  'ao-vivo': ['Ao vivo', 'Recebendo posições em tempo real'],
  polling: ['Atualizando', 'Atualização automática a cada 2 segundos'],
  offline: ['Sem conexão', 'O servidor não responde. Tentando novamente…'],
};
function renderConexao() {
  const [rotulo, dica] = ROTULO_CONEXAO[app.conexao] || ROTULO_CONEXAO.conectando;
  const c = $('#conexao');
  c.className = `conexao conexao-${app.conexao}`;
  c.title = dica;
  c.replaceChildren(el('span', { className: 'conexao-ponto' }), el('span', { className: 'rotulo' }, rotulo));
}

// --- Controles sobre o mapa ---
function botaoMapa(nome, rotulo, onclick, extra = {}) {
  return el('button', { className: 'ctrl-btn', type: 'button', title: rotulo, 'aria-label': rotulo, onclick, ...extra }, { icone: nome });
}
const btnSeguir = botaoMapa('seguir', 'Seguir o motoboy selecionado', () => definirSeguir(!app.seguir), { 'aria-pressed': 'false' });
const btnClientesVis = botaoMapa('olho', 'Ocultar clientes do mapa', () => {
  const vis = alternarVisibilidade();
  btnClientesVis.replaceChildren(el('span', {}, { icone: vis ? 'olho' : 'olhoFechado' }).firstChild);
  btnClientesVis.title = vis ? 'Ocultar clientes do mapa' : 'Mostrar clientes no mapa';
  btnClientesVis.setAttribute('aria-label', btnClientesVis.title);
});
const btnNovoCliente = botaoMapa('pinoMais', 'Novo cliente no mapa', () => (emModoMira() ? sairModoMira() : entrarModoMira()), { 'aria-pressed': 'false' });
$('#mapa-ctrl').append(
  el('div', { className: 'ctrl-grupo' },
    botaoMapa('enquadrar', 'Ver toda a frota', verTodos),
    btnSeguir),
  el('div', { className: 'ctrl-grupo' },
    btnNovoCliente,
    btnClientesVis,
    botaoMapa('historico', 'Replay de trilha', () => abrirReplay(app.sel))));

function definirSeguir(v) {
  app.seguir = v;
  btnSeguir.classList.toggle('ativo', v);
  btnSeguir.setAttribute('aria-pressed', String(v));
  if (v) {
    const pos = posicaoExibida(app.sel);
    if (pos) map.setView(pos, Math.max(map.getZoom(), 16));
  }
}
map.on('dragstart', () => { if (app.seguir) definirSeguir(false); });

function verTodos() {
  definirSeguir(false);
  enquadrar([...todasPosicoes(), RADAR_BASE()].map((p) => L.latLng(p[0], p[1])));
}
const RADAR_BASE = () => window.RADAR.base;

on('mira', (v) => { btnNovoCliente.classList.toggle('ativo', v); btnNovoCliente.setAttribute('aria-pressed', String(v)); });

// --- Ligações entre módulos ---
on('selecionar-moto', (id) => {
  if (!app.estado[id]) return;
  selecionar(id);
  if (telaPequena.matches) definirFolha('meio');
});
on('centralizar-moto', (id) => {
  const pos = posicaoExibida(id);
  if (pos) map.setView(pos, Math.max(map.getZoom(), 16), { animate: true });
});
on('abrir-replay', (id) => abrirReplay(id));
on('adicionar-parada', (c) => adicionarParada(c));
on('selecao', () => {
  realcarSelecao();
  renderFrota();
  renderDetalhe();
  desenharRota();
  if (app.seguir) definirSeguir(true);
});
on('estado', () => {
  if (!app.estado[app.sel]) {
    const primeiro = app.motoboys.find((m) => app.estado[String(m.id)]);
    if (primeiro) app.sel = String(primeiro.id);
  }
  atualizarMarcadores(app.estado);
  renderFrota();
  renderDetalhe();
  desenharRota();
  atualizarNotificacoes();
  renderResumo();
});
on('rota-calc', renderEstimativa);
on('clientes', aoMudarClientes);
on('conexao', renderConexao);
on('backend-novo', buscarResumo);
on('visibilidade', (visivel) => { if (visivel) sincronizarAnimacoes(); });

// --- Bottom sheet (celular) ---
const painel = $('#painel');
const ALTURAS = { min: 104, meio: 0.5, cheio: 0.88 };
let folha = 'min';
function alturaFolha(estado) {
  const v = ALTURAS[estado];
  return v < 1 ? Math.round(window.innerHeight * v) : v;
}
function definirFolha(estado) {
  folha = estado;
  painel.dataset.folha = estado;
  painel.style.removeProperty('--folha-h');
  painel.style.setProperty('--folha-h', `${alturaFolha(estado)}px`);
}
(function arrastarFolha() {
  const alca = $('#painel-alca');
  let y0 = 0;
  let h0 = 0;
  let arrastando = false;
  alca.addEventListener('pointerdown', (e) => {
    if (!telaPequena.matches) return;
    arrastando = true;
    y0 = e.clientY;
    h0 = painel.getBoundingClientRect().height;
    painel.classList.add('arrastando');
    alca.setPointerCapture(e.pointerId);
  });
  alca.addEventListener('pointermove', (e) => {
    if (!arrastando) return;
    const h = Math.max(ALTURAS.min, Math.min(window.innerHeight * 0.92, h0 + (y0 - e.clientY)));
    painel.style.setProperty('--folha-h', `${h}px`);
  });
  const soltar = (e) => {
    if (!arrastando) return;
    arrastando = false;
    painel.classList.remove('arrastando');
    const h = painel.getBoundingClientRect().height;
    if (Math.abs(e.clientY - y0) < 6) { definirFolha(folha === 'min' ? 'meio' : folha === 'meio' ? 'cheio' : 'min'); return; }
    const alvo = Object.keys(ALTURAS).reduce((melhor, k) => (Math.abs(alturaFolha(k) - h) < Math.abs(alturaFolha(melhor) - h) ? k : melhor), 'min');
    definirFolha(alvo);
  };
  alca.addEventListener('pointerup', soltar);
  alca.addEventListener('pointercancel', soltar);
  window.addEventListener('resize', () => { if (telaPequena.matches) definirFolha(folha); });
})();
definirFolha('min');

// --- Atalhos de teclado ---
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    if (haDialogoAberto()) { fecharDialogoTopo(); return; }
    if (emModoMira()) { sairModoMira(); return; }
    if (notifAberta()) { fecharNotif(); $('#btn-alertas').focus(); return; }
    if (replayAberto()) { fecharReplay(); return; }
    if (digitando(e.target)) e.target.blur();
    return;
  }
  if (haDialogoAberto() || digitando(e.target) || e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.key === '/') {
    e.preventDefault();
    if (telaPequena.matches && folha === 'min') definirFolha('meio');
    focarBusca();
  } else if (/^[1-9]$/.test(e.key)) {
    const mb = app.motoboys[Number(e.key) - 1];
    if (mb) { emit('selecionar-moto', String(mb.id)); emit('centralizar-moto', String(mb.id)); }
  }
});

// --- Inicialização ---
renderConexao();
montarNotificacoes();
montarDetalhe();
(async () => {
  try {
    app.motoboys = await get('/api/motoboys');
  } catch (e) {
    erro(e);
    app.motoboys = [];
  }
  app.sel = app.motoboys.length ? String(app.motoboys[0].id) : null;
  carregarClientes().catch(erro);
  const tr = iniciarTempoReal();
  on('acao-feita', (opcoes) => {
    tr.atualizarAgora();
    if (opcoes && opcoes.resumo) setTimeout(buscarResumo, 300);
  });
  buscarResumo();
  // Atualiza os "há X min" mesmo sem novas leituras
  setInterval(() => { if (!document.hidden) { renderFrota(); renderDetalhe(); } }, 15000);
})();
