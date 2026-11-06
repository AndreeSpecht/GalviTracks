/* Histórico de viagens: filtros com atalhos, tabela e exportação para Excel. */
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

const fmtDur = (m) => (m == null ? '—' : m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, '0')}`);

export function abrirHistorico() {
  const hoje = new Date();
  const inicio = el('input', { className: 'inp', type: 'date', 'aria-label': 'Data inicial', value: dataISO(hoje) });
  const fim = el('input', { className: 'inp', type: 'date', 'aria-label': 'Data final', value: dataISO(hoje) });
  const tbody = el('tbody');
  const totais = el('div', { className: 'totais' });

  const atalhos = [
    ['Hoje', () => [hoje, hoje]],
    ['7 dias', () => [new Date(hoje.getTime() - 6 * 864e5), hoje]],
    ['Este mês', () => [new Date(hoje.getFullYear(), hoje.getMonth(), 1), hoje]],
    ['Tudo', () => [null, null]],
  ];
  const chips = atalhos.map(([rotulo, fn], i) => el('button', {
    className: `chip${i === 0 ? ' ativo' : ''}`, type: 'button',
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
    tbody.replaceChildren(...Array.from({ length: 4 }, () => el('tr', { className: 'linha-skeleton' },
      ...Array.from({ length: 7 }, () => el('td', {}, el('span', { className: 'skeleton' }))))));
    let linhas;
    try { linhas = await get(`/api/get_historico?${filtros()}`); } catch (e) { erro(e); tbody.replaceChildren(); return; }
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
    subtitulo: 'Entregas finalizadas, com nota, horários e destinos',
    icone: 'historico',
    tamanho: 'xl',
    corpo: [
      el('div', { className: 'barra-filtros' },
        el('div', { className: 'chips' }, ...chips),
        el('div', { className: 'datas' }, inicio, el('span', { className: 'mudo' }, 'até'), fim)),
      totais,
      el('div', { className: 'tabela-rolagem' },
        el('table', { className: 'tabela' },
          el('thead', {}, el('tr', {}, ...['Data', 'Motoboy', 'Nota', 'Destinos', 'Saída', 'Chegada', 'Duração'].map((t) => el('th', {}, t)))),
          tbody)),
    ],
    rodape: [excel],
  });
  carregar();
}
