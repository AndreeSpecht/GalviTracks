/* Replay de trilha: painel flutuante sobre o mapa, com play/pausa, velocidades e trilha colorida por velocidade. */
import { get } from './api.js';
import { app } from './estado.js';
import { icone } from './icones.js';
import { camadaReplay, camadaRota, canvas, enquadrar, map, margens } from './mapa.js';
import { $, corSegura, dataISO, el, esc, limitar, rumo } from './util.js';
import { erro } from './ui.js';

/* global L */

const SEG_POR_SEG = 20;              // 1× = 20 s de trilha por segundo
const VELOCIDADES = [1, 4, 16];
const LACUNA_S = 120;                // sem leituras por mais que isso: pula
const FAIXAS = [                     // cor da trilha por velocidade (km/h)
  { ate: 5, cor: '#94a3b8', rotulo: 'parado' },
  { ate: 25, cor: '#22c55e', rotulo: 'até 25' },
  { ate: 45, cor: '#f59e0b', rotulo: '25–45' },
  { ate: Infinity, cor: '#ef4444', rotulo: '45+' },
];

let pontos = [];
let t = 0;
let tIni = 0;
let tFim = 0;
let tocando = false;
let mult = 1;
let ultimoQuadro = 0;
let indice = 0;
let marcador = null;
let ui = null;

const faixa = (v) => FAIXAS.find((f) => (v || 0) < f.ate) || FAIXAS[FAIXAS.length - 1];

export const replayAberto = () => !$('#replay').hidden;

export function abrirReplay(id = app.sel) {
  const raiz = $('#replay');
  const seletor = el('select', { className: 'inp inp-p', 'aria-label': 'Motoboy' },
    ...app.motoboys.map((m) => el('option', { value: String(m.id), selected: String(m.id) === String(id) }, m.nome)));
  const data = el('input', { className: 'inp inp-p', type: 'date', value: dataISO(), 'aria-label': 'Dia da trilha' });
  const btnPlay = el('button', { className: 'btn-play', type: 'button', 'aria-label': 'Reproduzir', disabled: true, onclick: () => (tocando ? pausar() : tocar()) });
  const slider = el('input', { type: 'range', min: '0', max: '1000', value: '0', className: 'replay-slider', 'aria-label': 'Posição na trilha', disabled: true });
  const hora = el('strong', { className: 'replay-hora' }, '--:--');
  const info = el('span', { className: 'replay-info mudo' }, 'Escolha o motoboy e o dia.');
  const vels = VELOCIDADES.map((v) => el('button', {
    className: `chip chip-p${v === mult ? ' ativo' : ''}`, type: 'button', 'aria-pressed': String(v === mult),
    onclick: (e) => { mult = v; vels.forEach((b) => { b.classList.toggle('ativo', b === e.currentTarget); b.setAttribute('aria-pressed', String(b === e.currentTarget)); }); },
  }, `${v}×`));

  slider.addEventListener('input', () => {
    t = tIni + (tFim - tIni) * (Number(slider.value) / 1000);
    indice = 0;
    posicionar(false);
  });
  seletor.addEventListener('change', carregar);
  data.addEventListener('change', carregar);

  raiz.replaceChildren(
    el('div', { className: 'replay-cab' },
      el('span', { className: 'replay-titulo' }, { icone: 'historico' }, 'Replay de trilha'),
      seletor, data,
      el('button', { className: 'btn-icone', type: 'button', 'aria-label': 'Fechar replay', title: 'Fechar (Esc)', onclick: fecharReplay }, { icone: 'x' })),
    el('div', { className: 'replay-ctrl' }, btnPlay, el('div', { className: 'replay-linha' }, slider, el('div', { className: 'replay-tempos' }, hora, info)), el('div', { className: 'chips' }, ...vels)),
    el('div', { className: 'replay-legenda' }, ...FAIXAS.map((f) => el('span', {}, el('i', { style: { background: f.cor } }), f.rotulo)), el('span', { className: 'mudo' }, 'km/h')));
  raiz.hidden = false;
  map.removeLayer(camadaRota); // a rota planejada atrapalha a leitura da trilha
  ui = { seletor, data, btnPlay, slider, hora, info };
  atualizarBotaoPlay();
  carregar();
}

export function fecharReplay() {
  pausar();
  camadaReplay.clearLayers();
  marcador = null;
  pontos = [];
  $('#replay').hidden = true;
  camadaRota.addTo(map);
}

async function carregar() {
  pausar();
  camadaReplay.clearLayers();
  marcador = null;
  ui.btnPlay.disabled = true;
  ui.slider.disabled = true;
  ui.info.textContent = 'Carregando…';
  const id = ui.seletor.value;
  try {
    pontos = await get(`/api/tracklog?id=${encodeURIComponent(id)}${ui.data.value ? `&data=${ui.data.value}` : ''}&simplificar=1`);
  } catch (e) { erro(e); pontos = []; }
  if (!pontos.length) {
    ui.info.textContent = 'Sem posições registradas neste dia.';
    ui.hora.textContent = '--:--';
    return;
  }
  // Trilha em trechos coloridos pela velocidade (agrupando trechos vizinhos da mesma faixa)
  let trecho = [[pontos[0].lat, pontos[0].lon]];
  let corAtual = faixa(pontos[1]?.velocidade).cor;
  for (let i = 1; i < pontos.length; i++) {
    const cor = faixa(pontos[i].velocidade).cor;
    const p = [pontos[i].lat, pontos[i].lon];
    if (cor !== corAtual) {
      trecho.push(p);
      L.polyline(trecho, { renderer: canvas, color: corAtual, weight: 5, opacity: 0.9, lineCap: 'round', interactive: false }).addTo(camadaReplay);
      trecho = [p];
      corAtual = cor;
    } else trecho.push(p);
  }
  if (trecho.length > 1) L.polyline(trecho, { renderer: canvas, color: corAtual, weight: 5, opacity: 0.9, lineCap: 'round', interactive: false }).addTo(camadaReplay);
  const ini = pontos[0];
  const fim = pontos[pontos.length - 1];
  L.circleMarker([ini.lat, ini.lon], { renderer: canvas, radius: 6, color: '#fff', weight: 2, fillColor: '#16a34a', fillOpacity: 1 }).bindTooltip('Início').addTo(camadaReplay);
  L.circleMarker([fim.lat, fim.lon], { renderer: canvas, radius: 6, color: '#fff', weight: 2, fillColor: '#0f172a', fillOpacity: 1 }).bindTooltip('Fim').addTo(camadaReplay);

  const m = app.estado[id];
  marcador = L.marker([ini.lat, ini.lon], {
    icon: L.divIcon({ className: 'moto-marcador', iconSize: [0, 0], html: `<div class="moto replay-moto com-rumo" style="--cor:${esc(corSegura(m && m.cor))}"><div class="moto-puck"><span class="moto-seta">${icone('seta')}</span></div></div>` }),
    interactive: false, zIndexOffset: 2000,
  }).addTo(camadaReplay);

  tIni = ini.timestamp;
  tFim = fim.timestamp;
  t = tIni;
  indice = 0;
  ui.btnPlay.disabled = false;
  ui.slider.disabled = false;
  const fmt = (ts) => new Date(ts * 1000).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
  ui.info.textContent = `${pontos.length} posições · ${fmt(tIni)} – ${fmt(tFim)}`;
  enquadrar(pontos.map((p) => L.latLng(p.lat, p.lon)), 17, $('#replay').offsetHeight + 16);
  posicionar(false);
}

function posicionar(seguir) {
  if (!pontos.length || !marcador) return;
  if (indice > 0 && pontos[indice].timestamp > t) indice = 0;
  while (indice < pontos.length - 1 && pontos[indice + 1].timestamp <= t) indice++;
  const a = pontos[indice];
  const b = pontos[Math.min(indice + 1, pontos.length - 1)];
  const k = b.timestamp > a.timestamp ? limitar((t - a.timestamp) / (b.timestamp - a.timestamp), 0, 1) : 0;
  const pos = [a.lat + (b.lat - a.lat) * k, a.lon + (b.lon - a.lon) * k];
  marcador.setLatLng(pos);
  const seta = marcador.getElement()?.querySelector('.moto-seta');
  if (seta && (a.lat !== b.lat || a.lon !== b.lon)) seta.style.transform = `rotate(${Number.isFinite(a.curso) ? a.curso : rumo(a.lat, a.lon, b.lat, b.lon)}deg)`;
  ui.slider.value = String(Math.round(((t - tIni) / Math.max(1, tFim - tIni)) * 1000));
  ui.hora.textContent = new Date(t * 1000).toLocaleTimeString('pt-BR');
  if (seguir) {
    // Desloca o mínimo necessário para manter o marcador visível acima do painel do replay.
    const m = margens($('#replay').offsetHeight + 16);
    map.panInside(pos, { paddingTopLeft: m.paddingTopLeft, paddingBottomRight: m.paddingBottomRight });
  }
}

function quadro(agora) {
  if (!tocando) return;
  const dt = Math.min(0.1, (agora - ultimoQuadro) / 1000);
  ultimoQuadro = agora;
  t += dt * SEG_POR_SEG * mult;
  // Pula períodos sem leitura (celular parado/desligado)
  const prox = pontos[indice + 1];
  if (prox && prox.timestamp - pontos[indice].timestamp > LACUNA_S && t > pontos[indice].timestamp + 2) t = Math.max(t, prox.timestamp);
  if (t >= tFim) { t = tFim; posicionar(true); pausar(); return; }
  posicionar(true);
  requestAnimationFrame(quadro);
}

function tocar() {
  if (!pontos.length) return;
  if (t >= tFim) { t = tIni; indice = 0; }
  tocando = true;
  ultimoQuadro = performance.now();
  atualizarBotaoPlay();
  requestAnimationFrame(quadro);
}

function pausar() {
  tocando = false;
  atualizarBotaoPlay();
}

function atualizarBotaoPlay() {
  if (!ui) return;
  ui.btnPlay.innerHTML = icone(tocando ? 'pausa' : 'play');
  ui.btnPlay.setAttribute('aria-label', tocando ? 'Pausar' : 'Reproduzir');
}

export function alternarPlay() { if (pontos.length) { if (tocando) pausar(); else tocar(); } }

