/* Cartões de resumo do dia no topo. Usa /api/resumo no backend novo; senão, calcula localmente. */
import { get } from './api.js';
import { app } from './estado.js';
import { $, dataISO, el } from './util.js';

const remoto = { entregas_hoje: null, km_hoje: null };
let ultimaBusca = 0;

const ITENS = [
  { chave: 'em_rota', rotulo: 'Em rota', classe: 'r-rota' },
  { chave: 'livres', rotulo: 'Disponíveis', classe: 'r-livre' },
  { chave: 'com_alerta', rotulo: 'Com alerta', classe: 'r-alerta' },
  { chave: 'entregas_hoje', rotulo: 'Entregas hoje', classe: '' },
  { chave: 'km_hoje', rotulo: 'Km hoje', classe: '' },
];

export async function buscarResumo() {
  ultimaBusca = Date.now();
  try {
    if (app.backendNovo) {
      const r = await get('/api/resumo');
      remoto.entregas_hoje = r.entregas_hoje;
      remoto.km_hoje = r.km_hoje;
    } else {
      const hoje = dataISO();
      const lista = await get(`/api/get_historico?inicio=${hoje}&fim=${hoje}`);
      remoto.entregas_hoje = lista.length;
    }
  } catch { /* mantém o último valor */ }
  renderResumo();
}

export function renderResumo() {
  if (Date.now() - ultimaBusca > 60000) buscarResumo();
  const motos = Object.values(app.estado);
  const valores = {
    em_rota: motos.filter((m) => m.status === 'EM_ROTA').length,
    livres: motos.filter((m) => m.status === 'LIVRE').length,
    com_alerta: motos.filter((m) => (m.alertas || []).length).length,
    entregas_hoje: remoto.entregas_hoje,
    km_hoje: remoto.km_hoje == null ? null : Number(remoto.km_hoje).toLocaleString('pt-BR', { maximumFractionDigits: 1 }),
  };
  const ul = $('#resumo');
  if (!ul.children.length) {
    ul.append(...ITENS.map((it) => el('li', { className: `r-item ${it.classe}`, dataset: { chave: it.chave } },
      el('strong', { className: 'r-valor' }, '–'), el('span', { className: 'r-rotulo' }, it.rotulo))));
  }
  for (const it of ITENS) {
    const li = ul.querySelector(`[data-chave="${it.chave}"]`);
    const v = valores[it.chave];
    li.hidden = v === null || v === undefined;
    li.querySelector('.r-valor').textContent = v ?? '–';
    if (it.chave === 'com_alerta') li.classList.toggle('ativo', v > 0);
  }
}
