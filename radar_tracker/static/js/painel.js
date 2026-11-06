/* Painel lateral: cartões da frota, detalhe do motoboy selecionado e ações da rota. */
import { acao } from './api.js';
import { app, emit, motoSel, nivelMaisGrave, online } from './estado.js';
import { icone } from './icones.js';
import { criarBusca } from './busca.js';
import { cadastrarCliente } from './clientes.js';
import { $, corSegura, duracaoDesde, el, iniciais, tempoDesde } from './util.js';
import { confirmar, erro, toast } from './ui.js';

const ICONE_ALERTA = { sem_sinal: 'semSinal', parado: 'relogio', bateria_baixa: 'bateria' };
const cartoes = new Map();
const rascunhoNota = new Map();
const assinaturas = {};

// --- Cartões da frota ---
function criarCartao(id, indice) {
  const li = el('li', {
    className: 'cartao', role: 'option', tabindex: '0', 'aria-selected': 'false', dataset: { id },
    onclick: () => emit('selecionar-moto', id),
    onkeydown: (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); emit('selecionar-moto', id); } },
  },
  el('span', { className: 'avatar' }, el('span', { className: 'avatar-ini' }), el('span', { className: 'avatar-status' })),
  el('div', { className: 'cartao-info' },
    el('div', { className: 'cartao-l1' }, el('strong', { className: 'cartao-nome' }), el('span', { className: 'pill' })),
    el('div', { className: 'cartao-meta' }),
    el('div', { className: 'cartao-alerta' })),
  indice < 9 ? el('kbd', { className: 'cartao-tecla', 'aria-hidden': 'true' }, String(indice + 1)) : null);
  return li;
}

function meta(m) {
  const partes = [];
  const on = online(m);
  const vel = Math.round(m.velocidade || 0);
  if (m.status === 'EM_ROTA') {
    partes.push(el('span', {}, { icone: 'rota' }, `${m.rota.length} parada${m.rota.length === 1 ? '' : 's'}`));
    const dur = duracaoDesde(m.hora_saida);
    if (dur) partes.push(el('span', {}, { icone: 'relogio' }, dur));
  }
  if (vel >= 3 && on !== false) partes.push(el('span', { className: 'meta-vel' }, `${vel} km/h`));
  if (m.bateria != null) {
    const baixa = (m.alertas || []).some((a) => a.tipo === 'bateria_baixa');
    partes.push(el('span', { className: baixa ? 'meta-ruim' : '' }, { icone: m.carregando ? 'carregando' : 'bateria' }, `${m.bateria}%`));
  }
  if (on === false || (m.status === 'LIVRE' && m.recebido_em)) {
    partes.push(el('span', { className: on === false ? 'meta-ruim' : 'mudo' }, tempoDesde(m.recebido_em) || ''));
  } else if (on === null) {
    partes.push(el('span', { className: 'mudo' }, 'sem GPS ainda'));
  }
  return partes;
}

export function renderFrota() {
  const ul = $('#frota');
  app.motoboys.forEach((mb, i) => {
    const id = String(mb.id);
    const m = app.estado[id];
    if (!m) return;
    let li = cartoes.get(id);
    if (!li) { li = criarCartao(id, i); cartoes.set(id, li); ul.append(li); }
    const nivel = nivelMaisGrave(m);
    const on = online(m);
    const sel = id === app.sel;
    li.style.setProperty('--cor', corSegura(m.cor));
    li.className = ['cartao', sel && 'sel', nivel && `nivel-${nivel}`, on === false && 'offline'].filter(Boolean).join(' ');
    li.setAttribute('aria-selected', String(sel));
    li.querySelector('.avatar-ini').textContent = iniciais(m.nome);
    li.querySelector('.avatar-status').className = `avatar-status ${on === true ? 'on' : on === false ? 'off' : 'nunca'}`;
    li.querySelector('.cartao-nome').textContent = m.nome;
    const pill = li.querySelector('.pill');
    pill.className = `pill ${m.status === 'EM_ROTA' ? 'pill-rota' : 'pill-livre'}`;
    pill.textContent = m.status === 'EM_ROTA' ? 'Em rota' : 'Disponível';
    li.querySelector('.cartao-meta').replaceChildren(...meta(m));
    const alertaEl = li.querySelector('.cartao-alerta');
    const a = (m.alertas || [])[0];
    alertaEl.replaceChildren(...(a ? [el('span', {}, { icone: ICONE_ALERTA[a.tipo] || 'alerta' }), a.mensagem] : []));
    alertaEl.hidden = !a;
  });
}

// --- Detalhe do motoboy selecionado ---
let busca = null;
const inpNota = el('input', {
  className: 'inp inp-nota', id: 'inp-nota', placeholder: 'Nº da nota / pedido', autocomplete: 'off', inputmode: 'text',
  'aria-label': 'Número da nota ou pedido', 'aria-describedby': 'nota-erro',
});
const notaErro = el('span', { className: 'campo-erro', id: 'nota-erro', 'aria-live': 'polite' });
inpNota.addEventListener('input', () => {
  rascunhoNota.set(app.sel, inpNota.value);
  notaErro.textContent = '';
  inpNota.removeAttribute('aria-invalid');
});
inpNota.addEventListener('keydown', (e) => { if (e.key === 'Enter') sairParaEntrega(); });

export function montarDetalhe() {
  busca = criarBusca({
    placeholder: 'Adicionar parada: cliente ou endereço…  ( / )',
    aoEscolher: async (r) => {
      if (r.tipo === 'cliente') { adicionarParada(r.cliente); return; }
      const c = await cadastrarCliente(r.lat, r.lon, { nome: r.nome, subtitulo: r.descricao || 'Endereço encontrado no mapa.' });
      if (c) adicionarParada(c);
    },
  });
  $('#detalhe').replaceChildren(
    el('div', { className: 'det-cab', id: 'det-cab' }),
    el('div', { className: 'det-alertas', id: 'det-alertas' }),
    el('div', { className: 'secao-cab' },
      el('h2', {}, 'Rota'), el('span', { className: 'contador', id: 'det-qtd' }),
      el('button', { className: 'btn btn-fantasma btn-p', id: 'btn-otimizar', type: 'button', onclick: otimizar, title: 'Reordena as paradas pela mais próxima (vizinho mais próximo)' },
        { icone: 'raio' }, 'Otimizar ordem')),
    el('div', { className: 'busca-slot', id: 'busca-slot' }, busca.raiz),
    el('ol', { className: 'paradas', id: 'paradas', 'aria-label': 'Paradas da rota' }));
  $('#rodape').replaceChildren(el('div', { className: 'estimativa', id: 'estimativa' }), el('div', { className: 'acoes-rota', id: 'acoes-rota' }));
}

export const focarBusca = () => busca && busca.focar();

function mudou(chave, valor) {
  const s = JSON.stringify(valor);
  if (assinaturas[chave] === s) return false;
  assinaturas[chave] = s;
  return true;
}

export function renderDetalhe() {
  const m = motoSel();
  if (!m) return;
  const livre = m.status === 'LIVRE';
  const nivel = nivelMaisGrave(m);
  const on = online(m);
  const cor = corSegura(m.cor);
  $('#painel').style.setProperty('--cor-sel', cor);

  if (mudou('cab', [app.sel, m.nome, cor, m.status, Math.round(m.velocidade || 0), m.bateria, m.carregando, on, tempoDesde(m.recebido_em), nivel])) {
    const vel = Math.round(m.velocidade || 0);
    $('#det-cab').replaceChildren(
      el('span', { className: 'avatar avatar-g', style: { '--cor': cor } }, el('span', { className: 'avatar-ini' }, iniciais(m.nome)),
        el('span', { className: `avatar-status ${on === true ? 'on' : on === false ? 'off' : 'nunca'}` })),
      el('div', { className: 'det-titulo' },
        el('h2', {}, m.nome),
        el('div', { className: 'det-sub' },
          el('span', { className: `pill ${livre ? 'pill-livre' : 'pill-rota'}` }, livre ? 'Disponível' : 'Em rota'),
          el('span', {}, on === null ? 'Aguardando o primeiro sinal do celular' : on ? (vel >= 3 ? `${vel} km/h` : 'Parado') : `Sem sinal · ${tempoDesde(m.recebido_em)}`),
          m.bateria != null && el('span', {}, { icone: m.carregando ? 'carregando' : 'bateria' }, `${m.bateria}%`))),
      el('div', { className: 'det-botoes' },
        el('button', { className: 'btn-icone', type: 'button', title: 'Centralizar no mapa', 'aria-label': 'Centralizar no mapa', onclick: () => emit('centralizar-moto', app.sel) }, { icone: 'seguir' }),
        el('button', { className: 'btn-icone', type: 'button', title: 'Replay da trilha', 'aria-label': 'Replay da trilha', onclick: () => emit('abrir-replay', app.sel) }, { icone: 'historico' })));
  }

  if (mudou('alertas', [app.sel, m.alertas])) {
    $('#det-alertas').replaceChildren(...(m.alertas || []).map((a) => el('div', { className: `aviso aviso-${a.nivel}`, role: 'alert' },
      { icone: ICONE_ALERTA[a.tipo] || 'alerta' }, el('span', {}, a.mensagem))));
  }

  busca.raiz.hidden = !livre;
  $('#det-qtd').textContent = m.rota.length ? `${m.rota.length} parada${m.rota.length === 1 ? '' : 's'}` : '';
  $('#btn-otimizar').hidden = !(livre && m.rota.length > 1);

  if (mudou('paradas', [app.sel, m.rota, livre, cor])) {
    const ol = $('#paradas');
    if (!m.rota.length) {
      ol.replaceChildren(el('li', { className: 'paradas-vazio' },
        el('span', { className: 'vazio-ic-wrap' }, { icone: 'pino' }),
        el('strong', {}, 'Nenhuma parada ainda'),
        el('span', {}, 'Busque um cliente acima ou clique num pino do mapa e escolha “Adicionar à rota”.')));
    } else {
      ol.replaceChildren(
        el('li', { className: 'parada-item parada-loja' }, el('span', { className: 'parada-num' }, { icone: 'loja' }), el('span', { className: 'parada-nome' }, 'Saída da loja')),
        ...m.rota.map((p, i) => el('li', { className: 'parada-item' },
          el('span', { className: 'parada-num' }, String(i + 1)),
          el('span', { className: 'parada-nome' }, p.nome),
          livre && el('button', { className: 'btn-icone btn-mini', type: 'button', title: 'Remover parada', 'aria-label': `Remover ${p.nome}`, onclick: () => removerParada(i, p.nome) }, { icone: 'x' }))),
        el('li', { className: 'parada-item parada-loja' }, el('span', { className: 'parada-num' }, { icone: 'bandeira' }), el('span', { className: 'parada-nome' }, 'Retorno à loja')));
    }
  }

  renderEstimativa();

  if (mudou('acoes', [app.sel, m.status, m.nota, m.hora_saida, m.rota.length])) {
    const area = $('#acoes-rota');
    if (livre) {
      inpNota.value = rascunhoNota.get(app.sel) || '';
      notaErro.textContent = '';
      area.replaceChildren(
        el('div', { className: 'campo-nota' }, el('span', { className: 'inp-ic' }, { icone: 'planilha' }, inpNota), notaErro),
        el('button', { className: 'btn btn-primario btn-g', type: 'button', onclick: sairParaEntrega, disabled: !m.rota.length },
          { icone: 'enviar' }, 'Sair para entrega'));
    } else {
      area.replaceChildren(
        el('div', { className: 'em-rota-info' },
          el('div', {}, el('small', {}, 'Nota / pedido'), el('strong', {}, m.nota || '—')),
          el('div', {}, el('small', {}, 'Saída'), el('strong', {}, m.hora_saida || '—')),
          el('div', {}, el('small', {}, 'Em rota há'), el('strong', { className: 'decorrido' }, duracaoDesde(m.hora_saida) || '—'))),
        el('button', { className: 'btn btn-sucesso btn-g', type: 'button', onclick: finalizar }, { icone: 'bandeira' }, 'Finalizar rota'));
    }
  } else if (!livre) {
    const d = $('#acoes-rota .decorrido');
    if (d) d.textContent = duracaoDesde(m.hora_saida) || '—';
  }
}

export function renderEstimativa() {
  const m = motoSel();
  const r = app.rotaCalc;
  const box = $('#estimativa');
  if (!box || !mudou('estimativa', [app.sel, r, m && m.rota.length])) return;
  if (!m || !m.rota.length || !r) { box.replaceChildren(); box.hidden = true; return; }
  box.hidden = false;
  if (r.carregando) {
    box.replaceChildren(el('div', { className: 'est-item' }, el('small', {}, 'Tempo estimado'), el('span', { className: 'skeleton' })),
      el('div', { className: 'est-item' }, el('small', {}, 'Distância'), el('span', { className: 'skeleton' })));
    return;
  }
  if (r.erro) { box.replaceChildren(el('div', { className: 'est-erro' }, { icone: 'alerta' }, 'Não foi possível calcular a rota.')); return; }
  const offline = r.fonte !== 'osrm';
  box.replaceChildren(
    el('div', { className: 'est-item' }, el('small', {}, 'Tempo estimado'), el('strong', {}, `${r.minutos} min`)),
    el('div', { className: 'est-item' }, el('small', {}, offline ? 'Distância (linha reta)' : 'Distância'), el('strong', {}, `${String(r.distancia_km).replace('.', ',')} km`)),
    el('span', { className: `est-fonte ${offline ? 'offline' : ''}`, title: offline ? 'Serviço de rotas indisponível: estimativa pela distância em linha reta.' : 'Trajeto calculado pelo OSRM (OpenStreetMap).' },
      offline ? 'Estimativa offline' : 'Rota OSRM'));
}

// --- Ações ---
export async function adicionarParada(c) {
  const m = motoSel();
  if (!m) return;
  if (m.status !== 'LIVRE') {
    toast(`${m.nome} está em rota. Finalize a rota atual para montar outra.`, 'aviso');
    return;
  }
  try {
    await acao('/api/add', { id: Number(app.sel), nome: c.nome, lat: c.lat, lon: c.lon }, 'Não foi possível adicionar a parada.');
    toast(`${c.nome} adicionado à rota de ${m.nome.split(' ')[0]}.`, 'sucesso', { duracao: 2500 });
    emit('acao-feita');
  } catch (e) { erro(e); }
}

async function removerParada(indice, nome) {
  try {
    await acao('/api/rm', { id: Number(app.sel), idx: indice }, 'Não foi possível remover a parada.');
    toast(`${nome} removido da rota.`, 'info', { duracao: 2500 });
    emit('acao-feita');
  } catch (e) { erro(e); }
}

async function otimizar() {
  try {
    await acao('/api/otimizar', { id: Number(app.sel) }, 'Não foi possível otimizar a rota.');
    toast('Paradas reordenadas pela mais próxima.', 'sucesso', { duracao: 2500 });
    emit('acao-feita');
  } catch (e) { erro(e); }
}

async function sairParaEntrega() {
  const m = motoSel();
  if (!m || m.status !== 'LIVRE') return;
  const nota = inpNota.value.trim();
  if (!m.rota.length) { toast('Adicione ao menos uma parada antes de sair.', 'aviso'); return; }
  if (!nota) {
    notaErro.textContent = 'Informe o número da nota para sair.';
    inpNota.setAttribute('aria-invalid', 'true');
    inpNota.focus();
    return;
  }
  try {
    await acao('/api/start', { id: Number(app.sel), nota }, 'Não foi possível iniciar a entrega.');
    rascunhoNota.delete(app.sel);
    toast(`Nota ${nota} · ${m.rota.length} parada${m.rota.length === 1 ? '' : 's'}`, 'sucesso', { titulo: `${m.nome} saiu para entrega` });
    emit('acao-feita', { resumo: true });
  } catch (e) { erro(e); }
}

async function finalizar() {
  const m = motoSel();
  if (!m) return;
  const ok = await confirmar(`A viagem da nota ${m.nota || '—'} será registrada no histórico e ${m.nome} ficará disponível.`,
    { titulo: `Finalizar a rota de ${m.nome}?`, ok: 'Finalizar rota', icone: 'bandeira' });
  if (!ok) return;
  try {
    await acao('/api/end', { id: Number(app.sel) }, 'Não foi possível finalizar a rota.');
    toast('Viagem registrada no histórico.', 'sucesso', { titulo: `${m.nome} finalizou a rota` });
    emit('acao-feita', { resumo: true });
  } catch (e) { erro(e); }
}

/** Ícone usado por outros módulos para o tipo de alerta. */
export const iconeAlerta = (tipo) => icone(ICONE_ALERTA[tipo] || 'alerta');
export const NOME_ICONE_ALERTA = ICONE_ALERTA;
