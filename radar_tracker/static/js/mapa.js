/* Mapa Leaflet: tiles por tema, camadas e pino da loja. */
import { icone } from './icones.js';
import { esc, telaPequena } from './util.js';

/* global L, RADAR */

// Tiles do OpenStreetMap (gratuitos, sem chave). O tema escuro é obtido por filtro CSS em .leaflet-tile-pane.
const ATRIBUICAO = '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>';
const URL_TILES = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';

export const base = RADAR.base;

export const map = L.map('mapa', {
  zoomControl: false,
  preferCanvas: true,
  zoomSnap: 0.5,
  wheelPxPerZoomLevel: 90,
}).setView(base, 14);

L.tileLayer(URL_TILES, { maxZoom: 19, attribution: ATRIBUICAO }).addTo(map);

L.control.zoom({ position: 'bottomright', zoomInTitle: 'Aproximar', zoomOutTitle: 'Afastar' }).addTo(map);
map.attributionControl.setPrefix(false);

/** O tema do mapa acompanha o da página pelo CSS; mantido como ponto único caso os tiles mudem. */
export function aplicarTemaMapa(tema) { map.getContainer().dataset.tema = tema; }

export const canvas = L.canvas({ padding: 0.5 });
export const camadaClientes = L.layerGroup().addTo(map);
export const camadaRota = L.layerGroup().addTo(map);
export const camadaReplay = L.layerGroup().addTo(map);
export const camadaMotos = L.layerGroup().addTo(map);

L.marker(base, {
  icon: L.divIcon({
    className: 'pino-loja',
    html: `<div class="loja">${icone('loja')}</div>`,
    iconSize: [40, 40],
    iconAnchor: [20, 20],
  }),
  keyboard: false,
  zIndexOffset: 500,
}).addTo(map).bindTooltip(`<strong>${esc(RADAR.empresa)}</strong><br>Saída e retorno das rotas`, { direction: 'top', offset: [0, -18] });

/** Margens para enquadramentos, descontando o painel/bottom sheet que cobre o mapa. */
export function margens(extraBaixo = 0) {
  if (telaPequena.matches) return { paddingTopLeft: [24, 80], paddingBottomRight: [24, Math.round(window.innerHeight * 0.45) + extraBaixo] };
  return { paddingTopLeft: [48, 48], paddingBottomRight: [72, 48 + extraBaixo] };
}

export function enquadrar(latlngs, maxZoom = 16, extraBaixo = 0) {
  const pontos = latlngs.filter(Boolean);
  if (!pontos.length) return;
  if (pontos.length === 1) { map.setView(pontos[0], Math.max(map.getZoom(), 15)); return; }
  map.fitBounds(L.latLngBounds(pontos), { ...margens(extraBaixo), maxZoom });
}
