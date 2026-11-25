/* Histórico de viagens: filtros com atalhos, tabela por viagem ou indicadores por motoboy e exportação para Excel. */
import { get } from './api.js';
import { vazio } from './clientes.js';
import { dataISO, el } from './util.js';
import { dialogo, erro } from './ui.js';

function minutosEntre(saida, chegada) {
  const p = (t) => (/^\d{1,2}:\d{2}$/.test(t || '') ? t.split(':').map(Number) : null);
  const a = p(saida);
  const b = p(chegada);
  if (!a || !b) return null;
  let m = b[0] * 60 + b[1] - (a[0] * 60 + a[1]);
  if (m < 0) m += 1440;
  return m;
}

const fmtDur = (m) => {
  if (m == null) return '—';
  m = Math.round(m);
  return m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, '0')}`;
};
const fmtNum = (n, casas = 1) => (n == null ? '—' : n.toLocaleString('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas }));
const fmtKm = (n) => (n == null ? '—' : `${fmtNum(n)} km`);

const COLS_VIAGENS = ['Data', 'Motoboy', 'Nota', 'Destinos', 'Saída', 'Chegada', 'Duração'];
const COLS_MOTOBOYS = ['Motoboy', 'Viagens', 'Destinos por viagem', 'Tempo médio de rota', 'Tempo total em rota', 'Km rodados', 'Km por viagem'];

function linhaIndicador(g, maxViagens, tag = 'td') {
  const c = (conteudo, classe = 'nowrap num') => el(tag, { className: classe }, conteudo);
  const largura = maxViagens ? Math.max(4, Math.round((g.viagens / maxViagens) * 100)) : 0;
  return el('tr', {},
    c(el('strong', {}, g.motoboy), 'nowrap'),
    c(tag === 'td'
      ? el('div', { className: 'ind-viagens' }, el('span', {}, String(g.viagens)),
        el('span', { className: 'ind-barra', 'aria-hidden': 'true' }, el('i', { style: { width: `${largura}%` } })))
      : String(g.viagens)),
    c(fmtNum(g.destinos_por_viagem)),
    c(fmtDur(g.tempo_medio_min)),
    c(fmtDur(g.tempo_total_min)),
    c(fmtKm(g.km)),
    c(fmtKm(g.km_por_viagem)));
}

export function abrirHistorico() {
  const hoje = new Date();
  const seteDias = new Date(hoje.getTime() - 6 * 864e5);
  // Abre nos últimos 7 dias: em "Hoje" a janela fica vazia antes da primeira entrega do dia.
  const inicio = el('input', { className: 'inp', type: 'date', 'aria-label': 'Data inicial', value: dataISO(seteDias) });
  const fim = el('input', { className: 'inp', type: 'date', 'aria-label': 'Data final', value: dataISO(hoje) });
  const thead = el('thead');
  const tbody = el('tbody');
  const tfoot = el('tfoot');
  const totais = el('div', { className: 'totais' });
  const nota = el('p', { className: 'ind-nota mudo', hidden: true });
  let visao = 'viagens';
  const botoesVisao = [['viagens', 'Viagens'], ['motoboys', 'Por motoboy']].map(([chave, rotulo]) => el('button', {
    className: `chip${chave === visao ? ' ativo' : ''}`, type: 'button', 'aria-pressed': String(chave === visao),
    onclick: () => {
      visao = chave;
      botoesVisao.forEach((b, i) => {
        const ativo = i === (chave === 'viagens' ? 0 : 1);
        b.classList.toggle('ativo', ativo);
        b.setAttribute('aria-pressed', String(ativo));
      });
      carregar();
    },
  }, rotulo));

  const atalhos = [
    ['Hoje', () => [hoje, hoje]],
    ['7 dias', () => [seteDias, hoje]],
    ['Este mês', () => [new Date(hoje.getFullYear(), hoje.getMonth(), 1), hoje]],
    ['Tudo', () => [null, null]],
  ];
  const chips = atalhos.map(([rotulo, fn], i) => el('button', {
    className: `chip${i === 1 ? ' ativo' : ''}`, type: 'button',
    onclick: (e) => {
      const [a, b] = fn();
      inicio.value = a ? dataISO(a) : '';
      fim.value = b ? dataISO(b) : '';
      chips.forEach((c) => c.classList.toggle('ativo', c === e.currentTarget));
      carregar();
    },
  }, rotulo));
  [inicio, fim].forEach((i) => i.addEventListener('change', () => { chips.forEach((c) => c.classList.remove('ativo')); carregar(); }));

  const filtros = () => {
    const p = new URLSearchParams();
    if (inicio.value) p.set('inicio', inicio.value);
    if (fim.value) p.set('fim', fim.value);
    return p.toString();
  };

  async function carregar() {
    const cols = visao === 'viagens' ? COLS_VIAGENS : COLS_MOTOBOYS;
    thead.replaceChildren(el('tr', {}, ...cols.map((t, i) => el('th', { className: visao === 'motoboys' && i ? 'num' : '' }, t))));
    tfoot.replaceChildren();
    nota.hidden = true;
    tbody.replaceChildren(...Array.from({ length: 4 }, () => el('tr', { className: 'linha-skeleton' },
      ...Array.from({ length: 7 }, () => el('td', {}, el('span', { className: 'skeleton' }))))));
    let linhas;
    let ind;
    try {
      [linhas, ind] = await Promise.all([
        get(`/api/get_historico?${filtros()}`),
        visao === 'motoboys' ? get(`/api/indicadores?${filtros()}`) : null,
      ]);
    } catch (e) { erro(e); tbody.replaceChildren(); return; }
    const durs = linhas.map((r) => minutosEntre(r.hora_saida, r.hora_chegada)).filter((x) => x != null);
    const media = durs.length ? Math.round(durs.reduce((a, b) => a + b, 0) / durs.length) : null;
    const motoboys = new Set(linhas.map((r) => r.motoboy)).size;
    totais.replaceChildren(
      el('div', {}, el('strong', {}, String(linhas.length)), el('span', {}, linhas.length === 1 ? 'viagem' : 'viagens')),
      el('div', {}, el('strong', {}, String(motoboys)), el('span', {}, motoboys === 1 ? 'motoboy' : 'motoboys')),
      el('div', {}, el('strong', {}, fmtDur(media)), el('span', {}, 'duração média')));
    if (!linhas.length) {
      tbody.replaceChildren(el('tr', {}, el('td', { colspan: '7' }, vazio('Nenhuma viagem registrada no período.', 'calendario'))));
      return;
    }
    if (ind) {
      const max = Math.max(...ind.motoboys.map((g) => g.viagens));
      tbody.replaceChildren(...ind.motoboys.map((g) => linhaIndicador(g, max)));
      tfoot.replaceChildren(linhaIndicador(ind.total, max, 'th'));
      const t = ind.total;
      nota.textContent = t.viagens_com_km === t.viagens
        ? 'Km pela trilha GPS de cada viagem. Tempo de rota: da saída à chegada.'
        : `Km pela trilha GPS: ${t.viagens_com_km} de ${t.viagens} viagens têm trilha (as demais não tiveram posições do celular ou passaram dos 90 dias de retenção). Tempo de rota: da saída à chegada.`;
      nota.hidden = false;
      return;
    }
    tbody.replaceChildren(...linhas.map((r) => el('tr', {},
      el('td', { className: 'mudo nowrap' }, r.data_viagem || ''),
      el('td', { className: 'nowrap' }, el('strong', {}, r.motoboy || '')),
      el('td', {}, el('span', { className: 'tag-nota' }, r.numero_nota || '—')),
      el('td', { className: 'col-destinos' }, r.destinos || ''),
      el('td', { className: 'nowrap' }, r.hora_saida || ''),
      el('td', { className: 'nowrap' }, r.hora_chegada || ''),
      el('td', { className: 'nowrap mudo' }, fmtDur(minutosEntre(r.hora_saida, r.hora_chegada))))));
  }

  const excel = el('a', { className: 'btn btn-sucesso', href: '#', download: '' }, { icone: 'planilha' }, 'Exportar Excel');
  excel.addEventListener('click', () => { excel.href = `/baixar_excel?${filtros()}`; });

  dialogo({
    titulo: 'Histórico de viagens',
    subtitulo: 'Entregas finalizadas e indicadores por motoboy',
    icone: 'historico',
    tamanho: 'xl',
    corpo: [
      el('div', { className: 'barra-filtros' },
        el('div', { className: 'chips' }, ...chips),
        el('div', { className: 'datas' }, inicio, el('span', { className: 'mudo' }, 'até'), fim)),
      totais,
      el('div', { className: 'chips visao', role: 'group', 'aria-label': 'Ver por' }, ...botoesVisao),
      el('div', { className: 'tabela-rolagem' }, el('table', { className: 'tabela' }, thead, tbody, tfoot)),
      nota,
    ],
    rodape: [excel],
  });
  carregar();
}
