/* Clientes: pinos no mapa, cadastro por "modo mira", edição e gestão em lista. */
import { acao, post } from './api.js';
import { app, carregarClientes, emit } from './estado.js';
import { icone } from './icones.js';
import { camadaClientes, map } from './mapa.js';
import { $, corSegura, el, esc, normalizar } from './util.js';
import { confirmar, dialogo, erro, formulario, toast } from './ui.js';

/* global L */

const COR_PADRAO = '#808080';
let visiveis = true;

function pinoCliente(cor) {
  return L.divIcon({
    className: 'pino-cliente',
    html: `<svg viewBox="0 0 28 36" width="26" height="34" aria-hidden="true"><path d="M14 1C7 1 1.5 6.4 1.5 13.3 1.5 22.6 14 35 14 35s12.5-12.4 12.5-21.7C26.5 6.4 21 1 14 1z" fill="${esc(cor)}" stroke="#fff" stroke-width="2"/><circle cx="14" cy="13.3" r="4.6" fill="#fff"/></svg>`,
    iconSize: [26, 34],
    iconAnchor: [13, 33],
    popupAnchor: [0, -30],
    tooltipAnchor: [10, -20],
  });
}

function popupCliente(c) {
  return el('div', { className: 'pop' },
    el('div', { className: 'pop-cab' },
      el('span', { className: 'pop-cor', style: { background: corSegura(c.cor, COR_PADRAO) } }),
      el('strong', {}, c.nome)),
    c.telefone && el('a', { className: 'pop-tel', href: `tel:${c.telefone.replace(/[^\d+]/g, '')}` }, { icone: 'telefone' }, c.telefone),
    el('div', { className: 'pop-acoes' },
      el('button', { className: 'btn btn-primario btn-p', type: 'button', onclick: () => { emit('adicionar-parada', c); map.closePopup(); } }, { icone: 'mais' }, 'Adicionar à rota'),
      el('button', { className: 'btn-icone', type: 'button', title: 'Editar', 'aria-label': `Editar ${c.nome}`, onclick: () => { map.closePopup(); editarCliente(c); } }, { icone: 'lapis' }),
      el('button', { className: 'btn-icone perigo', type: 'button', title: 'Apagar', 'aria-label': `Apagar ${c.nome}`, onclick: () => { map.closePopup(); apagarCliente(c); } }, { icone: 'lixo' })));
}

export function desenharClientes() {
  camadaClientes.clearLayers();
  for (const c of app.clientes) {
    L.marker([c.lat, c.lon], { icon: pinoCliente(corSegura(c.cor, COR_PADRAO)), keyboard: false })
      .bindPopup(() => popupCliente(c), { className: 'popup-radar', closeButton: false, minWidth: 220 })
      .bindTooltip(esc(c.nome), { direction: 'right', className: 'tt-cliente' })
      .addTo(camadaClientes);
  }
}

export function alternarVisibilidade() {
  visiveis = !visiveis;
  if (visiveis) camadaClientes.addTo(map);
  else map.removeLayer(camadaClientes);
  return visiveis;
}

const nomeExiste = (nome, ignorarId) =>
  app.clientes.some((c) => c.id !== ignorarId && normalizar(c.nome) === normalizar(nome));

/** Cadastra um cliente e devolve o objeto salvo (ou null). */
export async function cadastrarCliente(lat, lon, { nome = '', subtitulo } = {}) {
  const v = await formulario({
    titulo: 'Novo cliente',
    subtitulo: subtitulo || 'O pino fica no ponto escolhido no mapa.',
    icone: 'pinoMais',
    ok: 'Cadastrar',
    campos: [
      { nome: 'nome', rotulo: 'Nome da oficina / cliente', valor: nome, obrigatorio: true, placeholder: 'Ex.: Auto Center Silva' },
      { nome: 'telefone', rotulo: 'Telefone', tipo: 'tel', placeholder: '(47) 99999-0000' },
      { nome: 'cor', rotulo: 'Cor do pino', tipo: 'color', valor: '#2563eb' },
    ],
  });
  if (!v) return null;
  try {
    const existia = nomeExiste(v.nome);
    if (existia) toast(`Já existe um cliente chamado "${v.nome}". Usando o cadastro existente.`, 'aviso');
    const r = await post('/api/save_cli', { nome: v.nome, lat, lon });
    if (!existia) {
      if (v.telefone) await post('/api/update_client', { id: r.id, nome: v.nome, telefone: v.telefone });
      if (v.cor && v.cor !== COR_PADRAO) await post('/api/update_color', { id: r.id, cor: v.cor });
      toast(`${v.nome} cadastrado.`, 'sucesso');
    }
    await carregarClientes();
    return app.clientes.find((c) => c.id === r.id) || { id: r.id, nome: v.nome, lat, lon };
  } catch (e) { erro(e); return null; }
}

export async function editarCliente(c) {
  const v = await formulario({
    titulo: 'Editar cliente',
    icone: 'lapis',
    campos: [
      { nome: 'nome', rotulo: 'Nome', valor: c.nome, obrigatorio: true },
      { nome: 'telefone', rotulo: 'Telefone', tipo: 'tel', valor: c.telefone || '' },
      { nome: 'cor', rotulo: 'Cor do pino', tipo: 'color', valor: corSegura(c.cor, COR_PADRAO) },
    ],
  });
  if (!v) return;
  try {
    await post('/api/update_client', { id: c.id, nome: v.nome, telefone: v.telefone });
    if (v.cor && v.cor !== c.cor) await post('/api/update_color', { id: c.id, cor: v.cor });
    await carregarClientes();
    toast('Cliente atualizado.', 'sucesso');
  } catch (e) { erro(e); }
}

export async function apagarCliente(c) {
  const ok = await confirmar(`"${c.nome}" será removido do cadastro. As rotas e o histórico não são afetados.`,
    { titulo: 'Apagar cliente?', ok: 'Apagar', perigo: true, icone: 'lixo' });
  if (!ok) return;
  try {
    await acao('/api/apagar_cliente', { id: c.id });
    await carregarClientes();
    toast(`${c.nome} apagado.`, 'sucesso');
  } catch (e) { erro(e); }
}

// --- Modo mira: cadastrar cliente clicando no mapa ---
let mira = false;

export function emModoMira() { return mira; }

export function entrarModoMira() {
  if (mira) return;
  mira = true;
  document.body.classList.add('modo-mira');
  const aviso = $('#mira-aviso');
  aviso.replaceChildren(
    el('span', { className: 'mira-ic' }, { icone: 'mira' }),
    el('span', {}, el('strong', {}, 'Clique no mapa'), ' para posicionar o novo cliente'),
    el('button', { className: 'btn btn-sec btn-p', type: 'button', onclick: sairModoMira }, 'Cancelar (Esc)'));
  aviso.hidden = false;
  map.once('click', aoClicarMira);
  emit('mira', true);
}

export function sairModoMira() {
  if (!mira) return;
  mira = false;
  document.body.classList.remove('modo-mira');
  $('#mira-aviso').hidden = true;
  map.off('click', aoClicarMira);
  emit('mira', false);
}

async function aoClicarMira(e) {
  sairModoMira();
  const marcaTemp = L.marker(e.latlng, { icon: pinoCliente('#2563eb'), interactive: false }).addTo(map);
  await cadastrarCliente(e.latlng.lat, e.latlng.lng);
  map.removeLayer(marcaTemp);
}

// --- Gestão em lista ---
export function abrirGestao() {
  const busca = el('input', { className: 'inp', type: 'search', placeholder: 'Filtrar por nome ou telefone…', 'aria-label': 'Filtrar clientes' });
  const contador = el('span', { className: 'contador' });
  const tbody = el('tbody');
  const tabela = el('div', { className: 'tabela-rolagem' },
    el('table', { className: 'tabela' },
      el('thead', {}, el('tr', {}, el('th', {}, 'Cliente'), el('th', {}, 'Telefone'), el('th', { className: 'col-acoes' }, el('span', { className: 'sr' }, 'Ações')))),
      tbody));

  function render() {
    const termo = normalizar(busca.value);
    const lista = app.clientes.filter((c) => !termo || normalizar(c.nome).includes(termo) || String(c.telefone || '').includes(termo));
    contador.textContent = `${lista.length} de ${app.clientes.length}`;
    if (!lista.length) {
      tbody.replaceChildren(el('tr', {}, el('td', { colspan: '3' }, vazio(app.clientes.length ? 'Nenhum cliente encontrado.' : 'Nenhum cliente cadastrado ainda.'))));
      return;
    }
    tbody.replaceChildren(...lista.map((c) => el('tr', {},
      el('td', {}, el('span', { className: 'cel-cliente' }, el('span', { className: 'pop-cor', style: { background: corSegura(c.cor, COR_PADRAO) } }), c.nome)),
      el('td', { className: 'mudo' }, c.telefone || '—'),
      el('td', { className: 'col-acoes' },
        el('button', { className: 'btn-icone', type: 'button', title: 'Ver no mapa', 'aria-label': `Ver ${c.nome} no mapa`, onclick: () => { d.fechar(); map.setView([c.lat, c.lon], 17); } }, { icone: 'pino' }),
        el('button', { className: 'btn-icone', type: 'button', title: 'Editar', 'aria-label': `Editar ${c.nome}`, onclick: () => editarCliente(c) }, { icone: 'lapis' }),
        el('button', { className: 'btn-icone perigo', type: 'button', title: 'Apagar', 'aria-label': `Apagar ${c.nome}`, onclick: () => apagarCliente(c) }, { icone: 'lixo' })))));
  }

  busca.addEventListener('input', render);
  const atualizar = () => render();
  ouvintesGestao.add(atualizar);
  const d = dialogo({
    titulo: 'Clientes',
    subtitulo: 'Oficinas e clientes cadastrados no sistema',
    icone: 'usuarios',
    tamanho: 'lg',
    corpo: [el('div', { className: 'barra-filtros' }, el('span', { className: 'inp-ic' }, { icone: 'busca' }, busca), contador), tabela],
    rodape: [
      el('button', { className: 'btn btn-sec', type: 'button', onclick: () => { d.fechar(); entrarModoMira(); } }, { icone: 'pinoMais' }, 'Novo cliente no mapa'),
    ],
    aoFechar: () => ouvintesGestao.delete(atualizar),
  });
  render();
}

const ouvintesGestao = new Set();
export function aoMudarClientes() {
  desenharClientes();
  ouvintesGestao.forEach((fn) => fn());
}

export function vazio(texto, nomeIcone = 'info') {
  const e = el('div', { className: 'vazio' });
  e.innerHTML = icone(nomeIcone, 'vazio-ic');
  e.append(el('p', {}, texto));
  return e;
}
