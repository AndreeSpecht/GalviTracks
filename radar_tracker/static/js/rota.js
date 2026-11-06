/* Desenho da rota do motoboy selecionado (OSRM ou linha reta no modo offline). */
import { post } from './api.js';
import { app, emit } from './estado.js';
import { base, camadaRota, canvas, enquadrar } from './mapa.js';
import { corSegura, esc } from './util.js';

/* global L */

let chaveAtual = '';
let selAnterior = null;
let qtdAnterior = 0;

function pinoParada(numero, cor, concluida) {
  return L.divIcon({
    className: 'pino-parada',
    html: `<div class="parada${concluida ? ' concluida' : ''}" style="--cor:${esc(cor)}"><span>${numero}</span></div>`,
    iconSize: [30, 38],
    iconAnchor: [15, 36],
    tooltipAnchor: [12, -22],
  });
}

/** Redesenha quando a rota, a cor ou o motoboy selecionado mudarem (ou quando forcar = true). */
export async function desenharRota(forcar = false) {
  const m = app.estado[app.sel];
  const rota = (m && m.rota) || [];
  const chave = JSON.stringify([app.sel, rota, m && m.cor]);
  if (chave === chaveAtual && !forcar) return;
  const enquadrarDepois = forcar || selAnterior !== app.sel || rota.length > qtdAnterior;
  selAnterior = app.sel;
  qtdAnterior = rota.length;
  chaveAtual = chave;

  camadaRota.clearLayers();
  if (!rota.length) {
    app.rotaCalc = null;
    emit('rota-calc');
    return;
  }
  const cor = corSegura(m.cor);
  rota.forEach((p, i) => {
    L.marker([p.lat, p.lon], { icon: pinoParada(i + 1, cor), zIndexOffset: 200, keyboard: false })
      .bindTooltip(`<strong>${i + 1}.</strong> ${esc(p.nome)}`, { direction: 'right', className: 'tt-parada' })
      .addTo(camadaRota);
  });

  app.rotaCalc = { carregando: true };
  emit('rota-calc');
  let d;
  try {
    d = await post('/api/calc', { stops: rota });
  } catch (e) {
    if (chave !== chaveAtual) return;
    app.rotaCalc = { erro: e.message };
    emit('rota-calc');
    return;
  }
  if (chave !== chaveAtual) return; // a seleção mudou enquanto calculava

  const pontos = d.pontos && d.pontos.length ? d.pontos : [base, ...rota.map((p) => [p.lat, p.lon]), base];
  const offline = !(d.pontos && d.pontos.length);
  L.polyline(pontos, { renderer: canvas, color: '#ffffff', weight: 9, opacity: 0.85, lineJoin: 'round', interactive: false }).addTo(camadaRota);
  L.polyline(pontos, {
    renderer: canvas, color: cor, weight: 5, opacity: 0.95, lineJoin: 'round', interactive: false,
    dashArray: offline ? '8 10' : null,
  }).addTo(camadaRota);
  app.rotaCalc = d;
  emit('rota-calc');
  const replayAberto = !document.getElementById('replay').hidden; // o replay controla o enquadramento enquanto aberto
  if (enquadrarDepois && !replayAberto) enquadrar(pontos.map((p) => L.latLng(p[0], p[1])));
}

export function esquecerRota() { chaveAtual = ''; selAnterior = null; }
