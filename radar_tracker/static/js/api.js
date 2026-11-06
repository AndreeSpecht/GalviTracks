/* Acesso à API REST do servidor. Erros de rede/HTTP viram ErroApi com mensagem amigável. */

export class ErroApi extends Error {}

async function requisitar(url, opcoes) {
  let resp;
  try {
    resp = await fetch(url, opcoes);
  } catch {
    throw new ErroApi('Sem conexão com o servidor.');
  }
  let dados = null;
  try { dados = await resp.json(); } catch { /* resposta sem JSON */ }
  if (!resp.ok) throw new ErroApi((dados && dados.erro) || `Erro ${resp.status} no servidor.`);
  return dados;
}

export const get = (url) => requisitar(url);

export const post = (url, corpo) => requisitar(url, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(corpo),
});

/** POST de ação que responde {ok: 0|1}; lança ErroApi com `recusa` quando ok = 0. */
export async function acao(url, corpo, recusa) {
  const r = await post(url, corpo);
  if (r && r.ok === 0) throw new ErroApi(recusa || 'O servidor recusou a operação.');
  return r;
}
