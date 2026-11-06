/* Utilitários sem dependências. */
import { iconeEl } from './icones.js';

export const $ = (seletor, raiz = document) => raiz.querySelector(seletor);

export function esc(texto) {
  return String(texto ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

/**
 * Cria um elemento. Textos são sempre inseridos como texto (nunca HTML).
 * attrs: className, on<evento>, dataset, style (objeto), booleanos e demais atributos.
 * filhos: Node, string/número ou null/false (ignorados). { icone: 'nome' } insere um ícone.
 */
export function el(tag, attrs, ...filhos) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k.startsWith('on') && typeof v === 'function') e.addEventListener(k.slice(2), v);
    else if (k === 'className') e.className = v;
    else if (k === 'dataset') Object.assign(e.dataset, v);
    else if (k === 'style' && typeof v === 'object') Object.entries(v).forEach(([p, val]) => e.style.setProperty(p, val));
    else if (v === true) e.setAttribute(k, '');
    else e.setAttribute(k, v);
  }
  for (const f of filhos.flat()) {
    if (f === null || f === undefined || f === false || f === '') continue;
    if (f instanceof Node) e.append(f);
    else if (typeof f === 'object' && f.icone) e.append(iconeEl(f.icone, f.classe));
    else e.append(String(f));
  }
  return e;
}

export function debounce(fn, ms) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

export const limitar = (v, min, max) => Math.min(max, Math.max(min, v));

export function normalizar(texto) {
  return String(texto || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
}

export function primeiroNome(nome) { return String(nome || '').trim().split(/\s+/)[0] || '?'; }

export function iniciais(nome) {
  const partes = String(nome || '').trim().split(/\s+/).filter(Boolean);
  if (!partes.length) return '?';
  return (partes[0][0] + (partes.length > 1 ? partes[partes.length - 1][0] : '')).toUpperCase();
}

/** Aceita apenas cores #rrggbb / #rgb vindas do servidor. */
export function corSegura(cor, padrao = '#64748b') {
  return /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.test(String(cor || '')) ? cor : padrao;
}

export function haversineM(lat1, lon1, lat2, lon2) {
  const r = (g) => (g * Math.PI) / 180;
  const a = Math.sin(r(lat2 - lat1) / 2) ** 2 + Math.cos(r(lat1)) * Math.cos(r(lat2)) * Math.sin(r(lon2 - lon1) / 2) ** 2;
  return 6371000 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

/** Rumo em graus (0 = norte) de um ponto ao outro. */
export function rumo(lat1, lon1, lat2, lon2) {
  const r = (g) => (g * Math.PI) / 180;
  const y = Math.sin(r(lon2 - lon1)) * Math.cos(r(lat2));
  const x = Math.cos(r(lat1)) * Math.sin(r(lat2)) - Math.sin(r(lat1)) * Math.cos(r(lat2)) * Math.cos(r(lon2 - lon1));
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}

export const agoraS = () => Math.floor(Date.now() / 1000);

export function tempoDesde(ts) {
  if (!ts) return null;
  const s = Math.max(0, agoraS() - ts);
  if (s < 45) return 'agora';
  const min = Math.round(s / 60);
  if (min < 60) return `há ${min} min`;
  const h = Math.floor(min / 60);
  if (h < 24) return `há ${h} h${min % 60 ? ` ${min % 60} min` : ''}`;
  return `há ${Math.floor(h / 24)} d`;
}

export function duracaoDesde(hhmm) {
  if (!/^\d{1,2}:\d{2}$/.test(hhmm || '')) return null;
  const [h, m] = hhmm.split(':').map(Number);
  const agora = new Date();
  let min = agora.getHours() * 60 + agora.getMinutes() - (h * 60 + m);
  if (min < 0) min += 1440;
  return min < 60 ? `${min} min` : `${Math.floor(min / 60)} h ${min % 60} min`;
}

export function dataISO(d = new Date()) {
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export const movimentoReduzido = window.matchMedia('(prefers-reduced-motion: reduce)');
export const telaPequena = window.matchMedia('(max-width: 768px)');

export function lerPref(chave, padrao = null) {
  try { const v = localStorage.getItem(`radar.${chave}`); return v === null ? padrao : v; } catch { return padrao; }
}

export function gravarPref(chave, valor) {
  try { localStorage.setItem(`radar.${chave}`, valor); } catch { /* armazenamento indisponível */ }
}

export function digitando(alvo) {
  return alvo && (alvo.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(alvo.tagName));
}
