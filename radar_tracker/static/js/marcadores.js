/*
 * Marcadores dos motoboys: um marcador fixo por motoboy, atualizado no lugar.
 * A posição desliza da leitura anterior até a nova durante o intervalo esperado
 * até a próxima leitura (requestAnimationFrame), e a seta gira pelo menor ângulo.
 */
import { app, emit, nivelMaisGrave, online } from './estado.js';
import { icone } from './icones.js';
import { base, camadaMotos, canvas, map } from './mapa.js';
import { corSegura, esc, haversineM, iniciais, limitar, movimentoReduzido, primeiroNome, rumo, tempoDesde } from './util.js';

/* global L */

const SALTO_MAX_M = 1000;      // acima disso, move direto (sem animar)
const RAIO_LOJA_M = 30;        // motoboys parados na loja ficam lado a lado
const PRECISAO_HALO_M = 30;
const VEL_MOVENDO = 3;

const marcadores = new Map();  // id -> objeto
let loopAtivo = false;

function criar(id, m) {
  const cor = corSegura(m.cor);
  const marker = L.marker([m.lat_atual, m.lon_atual], {
    icon: L.divIcon({
      className: 'moto-marcador',
      iconSize: [0, 0],
      iconAnchor: [0, 0],
      html: `<div class="moto" style="--cor:${esc(cor)}">
        <div class="moto-rotulo"><span class="moto-nome"></span><span class="moto-bat"></span></div>
        <div class="moto-puck"><span class="moto-pulso"></span><span class="moto-seta">${icone('seta')}</span><span class="moto-ini"></span></div>
        <div class="moto-vel"></div>
      </div>`,
    }),
    keyboard: true,
    title: m.nome,
    riseOnHover: true,
  }).addTo(camadaMotos);
  marker.on('click', () => emit('selecionar-moto', id));
  return {
    id,
    marker,
    halo: null,
    pos: [m.lat_atual, m.lon_atual],
    ultimaLeitura: [m.lat_atual, m.lon_atual],
    anim: null,
    chegada: 0,
    intervaloMedio: 0,
    angulo: Number.isFinite(m.curso) ? m.curso : 0,
    temRumo: Number.isFinite(m.curso),
    assinatura: '',
  };
}

function girarPara(o, alvo) {
  // Acumula o ângulo para que a transição CSS sempre gire pelo menor caminho.
  const atual = o.angulo;
  const delta = ((alvo - (atual % 360) + 540) % 360) - 180;
  o.angulo = atual + delta;
  o.temRumo = true;
}

function moverPara(o, lat, lon) {
  const [la, lo] = o.ultimaLeitura;
  if (la === lat && lo === lon) return;
  const agora = performance.now();
  // Média dos intervalos recentes entre leituras: absorve a defasagem entre o envio do celular e a consulta.
  const intervalo = o.chegada ? agora - o.chegada : 2000;
  o.intervaloMedio = o.intervaloMedio ? o.intervaloMedio * 0.6 + intervalo * 0.4 : intervalo;
  o.chegada = agora;
  o.ultimaLeitura = [lat, lon];
  const dist = haversineM(o.pos[0], o.pos[1], lat, lon);
  if (dist > SALTO_MAX_M || movimentoReduzido.matches || document.hidden) {
    o.anim = null;
    definirPosicao(o, [lat, lon]);
    return;
  }
  // 20% a mais que o intervalo esperado: o marcador quase nunca para antes de a próxima leitura chegar.
  o.anim = { de: [...o.pos], para: [lat, lon], t0: agora, dur: limitar(o.intervaloMedio * 1.2, 500, 3500) };
  iniciarLoop();
}

function definirPosicao(o, pos) {
  o.pos = pos;
  o.marker.setLatLng(pos);
  if (o.halo) o.halo.setLatLng(pos);
  if (app.seguir && o.id === app.sel) map.panTo(pos, { animate: false });
}

function iniciarLoop() {
  if (loopAtivo) return;
  loopAtivo = true;
  requestAnimationFrame(quadro);
}

function quadro(t) {
  let continuar = false;
  for (const o of marcadores.values()) {
    if (!o.anim) continue;
    const k = limitar((t - o.anim.t0) / o.anim.dur, 0, 1);
    const { de, para } = o.anim;
    definirPosicao(o, [de[0] + (para[0] - de[0]) * k, de[1] + (para[1] - de[1]) * k]);
    if (k >= 1) o.anim = null;
    else continuar = true;
  }
  if (continuar) requestAnimationFrame(quadro);
  else loopAtivo = false;
}

/** Atualiza a parte visual só quando algo visível mudou. */
function aplicarVisual(o, m, deslocamento) {
  const elRaiz = o.marker.getElement();
  if (!elRaiz) return;
  const nivel = nivelMaisGrave(m);
  const on = online(m);
  const vel = Math.round(m.velocidade || 0);
  const movendo = vel >= VEL_MOVENDO && on !== false;
  const batBaixa = (m.alertas || []).some((a) => a.tipo === 'bateria_baixa');
  const sel = o.id === app.sel;
  const assinatura = JSON.stringify([m.nome, m.cor, nivel, m.status, vel, m.bateria, m.carregando, on, sel, movendo, o.temRumo, deslocamento, batBaixa]);
  if (assinatura === o.assinatura) return;
  o.assinatura = assinatura;

  const moto = elRaiz.firstElementChild;
  moto.style.setProperty('--cor', corSegura(m.cor));
  moto.style.setProperty('--dx', `${deslocamento}px`);
  moto.className = ['moto', sel && 'sel', m.status === 'EM_ROTA' && 'em-rota', nivel && `nivel-${nivel}`,
    on === false && 'offline', movendo && o.temRumo && 'com-rumo', deslocamento !== 0 && 'na-loja'].filter(Boolean).join(' ');
  moto.querySelector('.moto-nome').textContent = primeiroNome(m.nome);
  moto.querySelector('.moto-ini').textContent = iniciais(m.nome);
  const bat = moto.querySelector('.moto-bat');
  bat.textContent = batBaixa ? `${m.bateria}%` : '';
  bat.hidden = !batBaixa;
  const velEl = moto.querySelector('.moto-vel');
  velEl.textContent = movendo ? `${vel} km/h` : on === false ? (tempoDesde(m.recebido_em) || 'sem sinal') : '';
  velEl.hidden = !velEl.textContent;
  o.marker.setZIndexOffset(sel ? 1000 : nivel ? 600 : m.status === 'EM_ROTA' ? 300 : 0);
}

function atualizarSeta(o) {
  const e = o.marker.getElement();
  const seta = e && e.querySelector('.moto-seta');
  if (seta) seta.style.transform = `rotate(${o.angulo}deg)`;
}

function atualizarHalo(o, m) {
  const precisao = Number(m.precisao);
  if (Number.isFinite(precisao) && precisao > PRECISAO_HALO_M) {
    if (!o.halo) {
      o.halo = L.circle(o.pos, { renderer: canvas, radius: precisao, stroke: false, fillColor: corSegura(m.cor), fillOpacity: 0.12, interactive: false }).addTo(camadaMotos);
    } else o.halo.setRadius(precisao);
  } else if (o.halo) {
    camadaMotos.removeLayer(o.halo);
    o.halo = null;
  }
}

/** Sincroniza os marcadores com o estado recebido do servidor. */
export function atualizarMarcadores(estado) {
  // Motoboys livres na loja ficam lado a lado em vez de empilhados.
  const naLoja = Object.entries(estado)
    .filter(([, m]) => m.status === 'LIVRE' && m.lat_atual && haversineM(m.lat_atual, m.lon_atual, base[0], base[1]) < RAIO_LOJA_M)
    .map(([id]) => id);

  for (const [id, m] of Object.entries(estado)) {
    if (!m.lat_atual || !m.lon_atual) continue;
    let o = marcadores.get(id);
    if (!o) { o = criar(id, m); marcadores.set(id, o); }

    const [la, lo] = o.ultimaLeitura;
    if (Number.isFinite(m.curso)) girarPara(o, m.curso);
    else if (haversineM(la, lo, m.lat_atual, m.lon_atual) > 8) girarPara(o, rumo(la, lo, m.lat_atual, m.lon_atual));
    moverPara(o, m.lat_atual, m.lon_atual);

    const i = naLoja.indexOf(id);
    const deslocamento = i < 0 || naLoja.length < 2 ? 0 : Math.round((i - (naLoja.length - 1) / 2) * 44);
    aplicarVisual(o, m, deslocamento);
    atualizarSeta(o);
    atualizarHalo(o, m);
  }
  for (const [id, o] of marcadores) {
    if (!estado[id]) {
      camadaMotos.removeLayer(o.marker);
      if (o.halo) camadaMotos.removeLayer(o.halo);
      marcadores.delete(id);
    }
  }
}

/** Reaplica destaque de seleção sem esperar nova leitura. */
export function realcarSelecao() {
  for (const o of marcadores.values()) {
    o.assinatura = '';
    const m = app.estado[o.id];
    if (m) aplicarVisual(o, m, parseFloat(o.marker.getElement()?.firstElementChild?.style.getPropertyValue('--dx')) || 0);
  }
}

export const posicaoExibida = (id) => marcadores.get(String(id))?.pos || null;
export const todasPosicoes = () => [...marcadores.values()].map((o) => o.pos);

/** Ao voltar para a aba, encerra animações atrasadas de uma vez. */
export function sincronizarAnimacoes() {
  for (const o of marcadores.values()) {
    if (o.anim) { definirPosicao(o, o.anim.para); o.anim = null; }
  }
}
