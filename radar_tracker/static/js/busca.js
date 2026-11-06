/* Campo de busca com autocompletar: clientes cadastrados primeiro, depois endereços (Nominatim). */
import { get } from './api.js';
import { app } from './estado.js';
import { corSegura, debounce, el, normalizar } from './util.js';

const MAX_CLIENTES = 6;
let seq = 0;

/**
 * Cria o componente. aoEscolher({tipo: 'cliente', cliente} | {tipo: 'endereco', lat, lon, nome, descricao}).
 * Retorna { raiz, focar(), limpar(), desabilitar(bool) }.
 */
export function criarBusca({ placeholder, aoEscolher }) {
  const idLista = `busca-lista-${++seq}`;
  const input = el('input', {
    className: 'inp busca-inp', type: 'search', placeholder, autocomplete: 'off', spellcheck: 'false',
    role: 'combobox', 'aria-expanded': 'false', 'aria-controls': idLista, 'aria-autocomplete': 'list',
    'aria-label': placeholder,
  });
  const lista = el('ul', { className: 'busca-lista', id: idLista, role: 'listbox', hidden: true });
  const raiz = el('div', { className: 'busca' }, el('span', { className: 'inp-ic' }, { icone: 'busca' }, input), lista);

  let itens = [];
  let ativo = -1;
  let enderecos = { termo: '', estado: 'ocioso', lista: [] }; // ocioso | carregando | pronto

  function abrir(v) {
    lista.hidden = !v;
    input.setAttribute('aria-expanded', String(v));
  }

  function montar() {
    const termo = normalizar(input.value);
    if (!termo) { itens = []; abrir(false); return; }
    const clientes = app.clientes.filter((c) => normalizar(c.nome).includes(termo)).slice(0, MAX_CLIENTES);
    itens = clientes.map((c) => ({ tipo: 'cliente', cliente: c }));
    if (termo.length >= 3 && enderecos.termo === termo) {
      if (enderecos.estado === 'carregando') itens.push({ tipo: 'carregando' });
      else enderecos.lista.forEach((r) => itens.push({ tipo: 'endereco', ...r }));
    }
    if (!itens.length) itens.push({ tipo: termo.length < 3 ? 'curto' : 'vazio' });
    if (ativo >= itens.length || (ativo >= 0 && !escolhivel(itens[ativo]))) ativo = -1;
    render();
    abrir(true);
    lista.scrollIntoView({ block: 'nearest' });
  }

  const escolhivel = (it) => it && (it.tipo === 'cliente' || it.tipo === 'endereco');

  function render() {
    let grupo = null;
    const filhos = [];
    itens.forEach((it, i) => {
      const g = it.tipo === 'cliente' ? 'Clientes cadastrados' : it.tipo === 'endereco' || it.tipo === 'carregando' ? 'Endereços' : null;
      if (g && g !== grupo) { grupo = g; filhos.push(el('li', { className: 'busca-grupo', role: 'presentation' }, g)); }
      if (it.tipo === 'cliente') {
        filhos.push(el('li', opcao(i), el('span', { className: 'busca-cor', style: { background: corSegura(it.cliente.cor, '#808080') } }),
          el('span', { className: 'busca-txt' }, el('strong', {}, it.cliente.nome), it.cliente.telefone && el('small', {}, it.cliente.telefone))));
      } else if (it.tipo === 'endereco') {
        filhos.push(el('li', opcao(i), el('span', { className: 'busca-ic' }, { icone: 'pino' }),
          el('span', { className: 'busca-txt' }, el('strong', {}, it.nome), el('small', {}, it.descricao))));
      } else if (it.tipo === 'carregando') {
        filhos.push(el('li', { className: 'busca-info', role: 'presentation' }, el('span', { className: 'spinner' }), 'Procurando endereço…'));
      } else {
        filhos.push(el('li', { className: 'busca-info', role: 'presentation' },
          it.tipo === 'curto' ? 'Digite ao menos 3 letras para buscar endereços.' : 'Nada encontrado no cadastro nem no mapa.'));
      }
    });
    lista.replaceChildren(...filhos);
    input.setAttribute('aria-activedescendant', ativo >= 0 ? `${idLista}-${ativo}` : '');
  }

  function opcao(i) {
    return {
      id: `${idLista}-${i}`, role: 'option', className: `busca-item${i === ativo ? ' ativo' : ''}`, 'aria-selected': String(i === ativo),
      onmousedown: (e) => { e.preventDefault(); escolher(i); },
      onmousemove: () => { if (ativo !== i) { ativo = i; render(); } },
    };
  }

  function escolher(i) {
    const it = itens[i];
    if (!escolhivel(it)) return;
    limpar();
    aoEscolher(it.tipo === 'cliente' ? { tipo: 'cliente', cliente: it.cliente } : it);
  }

  const buscarEndereco = debounce(async (termoOriginal) => {
    const termo = normalizar(termoOriginal);
    if (termo.length < 3 || normalizar(input.value) !== termo) return;
    enderecos = { termo, estado: 'carregando', lista: [] };
    montar();
    let resultado = [];
    try { resultado = await get(`/api/buscar?q=${encodeURIComponent(termoOriginal.trim())}`); } catch { /* sem resultado */ }
    if (enderecos.termo !== termo) return;
    enderecos = {
      termo,
      estado: 'pronto',
      lista: (resultado || []).filter((r) => r && r.lat && r.lon).map((r) => ({
        nome: String(r.display_name || '').split(',')[0],
        descricao: String(r.display_name || '').split(',').slice(1, 4).join(',').trim(),
        lat: parseFloat(r.lat),
        lon: parseFloat(r.lon),
      })),
    };
    if (document.activeElement === input) montar();
  }, 400);

  input.addEventListener('input', () => {
    ativo = -1;
    montar();
    buscarEndereco(input.value);
  });
  input.addEventListener('focus', () => { if (input.value.trim()) montar(); });
  input.addEventListener('blur', () => setTimeout(() => abrir(false), 120));
  input.addEventListener('keydown', (e) => {
    const escolhiveis = itens.map((it, i) => (escolhivel(it) ? i : -1)).filter((i) => i >= 0);
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      if (lista.hidden) montar();
      if (!escolhiveis.length) return;
      const pos = escolhiveis.indexOf(ativo);
      const prox = e.key === 'ArrowDown' ? (pos + 1) % escolhiveis.length : (pos <= 0 ? escolhiveis.length - 1 : pos - 1);
      ativo = escolhiveis[prox];
      render();
      lista.querySelector('.ativo')?.scrollIntoView({ block: 'nearest' });
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const alvo = ativo >= 0 ? ativo : escolhiveis[0];
      if (alvo !== undefined) escolher(alvo);
      else buscarEndereco(input.value);
    } else if (e.key === 'Escape') {
      if (!lista.hidden || input.value) {
        e.stopPropagation();
        if (lista.hidden) limpar(); else abrir(false);
      }
    }
  });

  function limpar() {
    input.value = '';
    itens = [];
    ativo = -1;
    abrir(false);
  }

  return {
    raiz,
    focar() { input.focus(); input.select(); },
    limpar,
    desabilitar(v) { input.disabled = v; },
  };
}
