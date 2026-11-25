/* Usuário logado: menu do rodapé (como o NavUser do ERP), troca de senha, saída e gestão de usuários. */
import { acao, get, post } from './api.js';
import { icone } from './icones.js';
import { confirmar, dialogo, erro, formulario, toast } from './ui.js';
import { $, el, iniciais } from './util.js';

const eu = window.RADAR.usuario || {};
const PERFIS = [['operador', 'Operador'], ['gestor', 'Gestor']];
let menu = null;

export function montarUsuario() {
  const botao = $('#btn-usuario');
  $('#nav-avatar').textContent = iniciais(eu.nome || window.RADAR.empresa);
  $('#nav-usuario-seta').innerHTML = icone('baixo');
  botao.addEventListener('click', (e) => { e.stopPropagation(); if (menu) fecharMenu(); else abrirMenu(botao); });
  document.addEventListener('click', (e) => { if (menu && !menu.contains(e.target)) fecharMenu(); });
  window.addEventListener('resize', fecharMenu);
}

export const menuAberto = () => menu !== null;

export function fecharMenu() {
  if (!menu) return;
  menu.remove();
  menu = null;
  $('#btn-usuario').setAttribute('aria-expanded', 'false');
}

function abrirMenu(botao) {
  const item = (nome, texto, fn) => el('button', { className: 'menu-item', type: 'button', role: 'menuitem', onclick: () => { fecharMenu(); fn(); } }, { icone: nome }, texto);
  menu = el('div', { className: 'menu-usuario', role: 'menu', 'aria-label': 'Conta' },
    el('div', { className: 'menu-usuario-cab' },
      el('span', { className: 'nav-avatar' }, iniciais(eu.nome)),
      el('div', {}, el('strong', {}, eu.nome), el('span', {}, `${eu.usuario} · ${eu.perfil === 'gestor' ? 'Gestor' : 'Operador'}`))),
    el('div', { className: 'menu-sep' }),
    eu.perfil === 'gestor' && item('usuarios', 'Usuários', abrirUsuarios),
    item('lapis', 'Trocar minha senha', () => trocarSenha(eu, true)),
    el('div', { className: 'menu-sep' }),
    item('enviar', 'Sair', sair));
  document.body.append(menu);
  // Abre ao lado do menu lateral (como o dropdown side="right" do ERP); no celular, acima do botão.
  const r = botao.getBoundingClientRect();
  const nav = $('#nav').getBoundingClientRect();
  const lado = window.innerWidth > 768;
  menu.style.left = `${lado ? nav.right + 4 : r.left}px`;
  menu.style.bottom = `${window.innerHeight - (lado ? r.bottom : r.top - 4)}px`;
  botao.setAttribute('aria-expanded', 'true');
  const primeiro = menu.querySelector('.menu-item');
  if (primeiro) primeiro.focus();
  menu.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') { fecharMenu(); botao.focus(); }
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      const itens = [...menu.querySelectorAll('.menu-item')];
      const i = itens.indexOf(document.activeElement);
      itens[(i + (e.key === 'ArrowDown' ? 1 : itens.length - 1)) % itens.length].focus();
    }
  });
}

async function sair() {
  try {
    await post('/logout', {});
  } finally {
    window.location.assign('/login');
  }
}

async function trocarSenha(usuario, propria) {
  const v = await formulario({
    titulo: propria ? 'Trocar minha senha' : `Nova senha para ${usuario.nome}`,
    subtitulo: propria ? 'A senha nova vale a partir do próximo login.' : 'Passe a senha nova para o usuário.',
    icone: 'lapis',
    ok: 'Salvar senha',
    campos: [
      { nome: 'senha', rotulo: 'Senha nova', tipo: 'password', obrigatorio: true, autocomplete: 'new-password', dica: 'Pelo menos 6 caracteres.' },
      { nome: 'confirmacao', rotulo: 'Confirme a senha', tipo: 'password', obrigatorio: true, autocomplete: 'new-password' },
    ],
  });
  if (!v) return;
  if (v.senha !== v.confirmacao) { toast('As senhas não conferem.', 'erro'); return; }
  try {
    await acao(`/api/usuarios/${usuario.id}/senha`, { senha: v.senha });
    toast('Senha alterada.', 'sucesso');
  } catch (e) { erro(e); }
}

export function abrirUsuarios() {
  const tbody = el('tbody');
  const tabela = el('div', { className: 'tabela-rolagem' },
    el('table', { className: 'tabela' },
      el('thead', {}, el('tr', {}, el('th', {}, 'Nome'), el('th', {}, 'Usuário'), el('th', {}, 'Perfil'),
        el('th', { className: 'col-acoes' }, el('span', { className: 'sr' }, 'Ações')))),
      tbody));

  async function carregar() {
    try {
      const lista = await get('/api/usuarios');
      tbody.replaceChildren(...lista.map((u) => el('tr', {},
        el('td', {}, el('span', { className: 'cel-cliente' }, el('span', { className: 'nav-avatar' }, iniciais(u.nome)), u.nome,
          u.id === eu.id ? el('span', { className: 'mudo' }, ' (você)') : null)),
        el('td', { className: 'mudo' }, u.usuario),
        el('td', {}, el('span', { className: `perfil perfil-${u.perfil}` }, u.perfil === 'gestor' ? 'Gestor' : 'Operador')),
        el('td', { className: 'col-acoes' },
          el('button', { className: 'btn-icone', type: 'button', title: 'Definir senha nova', 'aria-label': `Definir senha nova para ${u.nome}`, onclick: () => trocarSenha(u, u.id === eu.id) }, { icone: 'lapis' }),
          u.id !== eu.id && el('button', { className: 'btn-icone perigo', type: 'button', title: 'Remover acesso', 'aria-label': `Remover acesso de ${u.nome}`, onclick: () => remover(u) }, { icone: 'lixo' })))));
    } catch (e) { erro(e); }
  }

  async function novo() {
    const v = await formulario({
      titulo: 'Novo usuário',
      subtitulo: 'Quem vai usar o painel do GalviTracks',
      icone: 'usuarios',
      ok: 'Criar usuário',
      campos: [
        { nome: 'nome', rotulo: 'Nome', obrigatorio: true, placeholder: 'Ex.: Maria Souza' },
        { nome: 'usuario', rotulo: 'Usuário', obrigatorio: true, placeholder: 'Ex.: maria', dica: 'Sem espaços. É o que a pessoa digita para entrar.' },
        { nome: 'senha', rotulo: 'Senha', tipo: 'password', obrigatorio: true, autocomplete: 'new-password', dica: 'Pelo menos 6 caracteres.' },
        { nome: 'perfil', rotulo: 'Perfil', opcoes: PERFIS, valor: 'operador', dica: 'O gestor também cadastra e remove usuários.' },
      ],
    });
    if (!v) return;
    try {
      await acao('/api/usuarios', v);
      toast(`Usuário ${v.usuario} criado.`, 'sucesso');
      carregar();
    } catch (e) { erro(e); }
  }

  async function remover(u) {
    if (!await confirmar(`${u.nome} não vai mais conseguir entrar no GalviTracks.`, { titulo: 'Remover acesso?', ok: 'Remover', perigo: true })) return;
    try {
      await acao(`/api/usuarios/${u.id}/remover`, {});
      toast('Acesso removido.', 'sucesso');
      carregar();
    } catch (e) { erro(e); }
  }

  dialogo({
    titulo: 'Usuários',
    subtitulo: 'Quem pode entrar no painel',
    icone: 'usuarios',
    tamanho: 'lg',
    corpo: tabela,
    rodape: [el('button', { className: 'btn btn-primario', type: 'button', onclick: novo }, { icone: 'mais' }, 'Novo usuário')],
  });
  carregar();
}
