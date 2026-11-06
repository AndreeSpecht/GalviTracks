/* Estado compartilhado do painel e eventos entre módulos. */
import { get } from './api.js';
import { agoraS } from './util.js';

export const app = {
  motoboys: [],        // [{id, nome, cor}] na ordem do config
  estado: {},          // { "<id>": motoboy } vindo de /api/estado ou /api/stream
  sel: null,           // id (texto) do motoboy selecionado
  clientes: [],
  conexao: 'conectando', // conectando | ao-vivo | polling | offline
  backendNovo: false,  // true quando o servidor implementa o contrato de tempo real
  rotaCalc: null,      // resultado de /api/calc da rota selecionada
  seguir: false,
};

const ouvintes = {};
export function on(evento, fn) { (ouvintes[evento] ||= []).push(fn); }
export function emit(evento, dados) { (ouvintes[evento] || []).forEach((fn) => fn(dados)); }

export const motoSel = () => app.estado[app.sel];

export function selecionar(id) {
  app.sel = String(id);
  emit('selecao', app.sel);
}

export async function carregarClientes() {
  app.clientes = await get('/api/clientes');
  emit('clientes', app.clientes);
}

const SEM_SINAL_S = 180;

/** true / false / null (nunca se comunicou). Usa o campo do servidor quando existir. */
export function online(m) {
  if (typeof m.online === 'boolean') return m.online;
  if (!m.recebido_em) return null;
  return agoraS() - m.recebido_em < SEM_SINAL_S;
}

export const ORDEM_NIVEL = { critico: 0, alerta: 1, aviso: 2 };

export function nivelMaisGrave(m) {
  const a = (m && m.alertas) || [];
  return a.length ? a.slice().sort((x, y) => ORDEM_NIVEL[x.nivel] - ORDEM_NIVEL[y.nivel])[0].nivel : null;
}

export function todosAlertas() {
  const lista = [];
  for (const [mid, m] of Object.entries(app.estado)) {
    for (const a of m.alertas || []) lista.push({ ...a, mid, m });
  }
  return lista.sort((a, b) => ORDEM_NIVEL[a.nivel] - ORDEM_NIVEL[b.nivel]);
}
