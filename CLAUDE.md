# CLAUDE.md: contexto do projeto GalviTracks

Guia para o Claude (ou qualquer pessoa) continuar o trabalho com o contexto completo. Leia junto com o `README.md` e o `docs/cronograma.md`.

## O projeto

- **GalviTracks**: sistema de rastreamento de motoboys em tempo real da **Radar Auto Peças** (Jaraguá do Sul/SC), desenvolvido pela **Galvitech Ltda**.
- É o **TCC de Engenharia de Software** do André Gustavo Specht (Católica de SC, 8º período, 2026/2, Prof.ª Jessica Aline Karsten). **Defesa em 04/12/2026.**
- Repositório: https://github.com/AndreeSpecht/GalviTracks (renomeado de `rastreamento-motoboys-galvitech` em 06/11/2026; o GitHub redireciona o nome antigo). Branch principal: `main`.
- Pasta local no PC da loja: `C:\Users\radar\OneDrive\Desktop\GalviTracks` (Windows 11, dentro do OneDrive). Substituiu a pasta antiga `RadarPecas_Instalador`.
- Escopo: só o rastreamento. Sistema independente, sem integração com outros sistemas da loja; clientes cadastrados no próprio sistema e nº da nota digitado à mão.

## Arquitetura

```
Celular (app OwnTracks, modo HTTP) --POST /api/gps/owntracks--> túnel ngrok --> servidor Python
Servidor: Flask + waitress (run.py), estado da frota em memória + data/sessao.json, SQLite (data/radar.db, WAL)
Painel web: Leaflet + módulos ES, tempo real por SSE (/api/stream) com volta ao polling de 2 s
Rotas: OSRM público (fallback offline por Haversine) · Endereços: Nominatim · Tiles: OpenStreetMap (CARTO exige chave)
```

| Caminho | Conteúdo |
|---|---|
| `radar_tracker/__init__.py` | `create_app(config, motoboys)`, `__version__ = "0.8.0"` |
| `radar_tracker/api.py` | todas as rotas, OwnTracks, Excel e o **bloqueio de acesso externo** (`_proteger_acesso_externo`) |
| `radar_tracker/config.py` | `Config` lida do `.env`; `carregar_motoboys()` (`config/motoboys.json` ou o `.example`) |
| `radar_tracker/frota.py` | estado dos motoboys, filtro de GPS, sessão gravada em segundo plano |
| `radar_tracker/db.py` | SQLite: esquema, migrações, retenção da trilha |
| `radar_tracker/stream.py` | SSE (`Streams`, `eventos`) |
| `radar_tracker/alertas.py` | sem sinal, parado fora de cliente, bateria baixa |
| `radar_tracker/geo.py`, `roteamento.py` | haversine, vizinho mais próximo, OSRM/Nominatim |
| `radar_tracker/static/js/main.js` | entrada do painel (módulos: mapa, marcadores, tempo-real, rota, busca, clientes, historico, replay, resumo, notificacoes, ui...) |
| `radar_tracker/static/css/app.css` | design system com tema claro/escuro |
| `run.py` | ponto de entrada; `criar_servidor()` configura o waitress |
| `scripts/simular_motoboy.py` | simulador do OwnTracks (`--tid`, `--todos`, `--token`, `--bateria`, `--parar-por`, `--cair-sinal`) |
| `scripts/seed_demo.py` | clientes fictícios |
| `scripts/verificar_stream.py` | verificação real do SSE com waitress |
| `scripts/windows/launcher/` | código-fonte do `GalviTracks.exe` (`GalviTracks.cs`, C# 5) + `compilar.bat` |
| `scripts/windows/tunel_ngrok.bat` | abre só o túnel |
| `scripts/docs/` | gerador do cronograma: `dados.js` (fonte) + `gerar.js` → `.docx` e `.md` |
| `tests/` | pytest (105 testes) |

Documentação: `docs/` (instalacao, requisitos, arquitetura, api, banco-de-dados, desenvolvimento, cronograma) e `CHANGELOG.md`.

## GalviTracks.exe (Windows)

- Fica na raiz e é versionado. Um clique: na primeira vez cria o `.venv` e instala as dependências (refaz quando o hash do `requirements.txt` muda), copia `.env.example`/`motoboys.example.json` se faltarem, abre o túnel ngrok, sobe `run.py` e abre o painel. Fechar a janela encerra tudo (job object por processo filho). Se já estiver rodando, só abre o painel.
- Opções: `--sem-tunel`, `--sem-navegador`.
- O túnel só abre se `NGROK_DOMAIN` **e** `OWNTRACKS_TOKEN` estiverem no `.env` e existir `tools\ngrok.exe` (ou ngrok no PATH). Log em `data\ngrok.log`.
- **Recompilar depois de mudar o `.cs`**: no PowerShell, `& cmd.exe /c "C:\Users\radar\OneDrive\Desktop\GalviTracks\scripts\windows\launcher\compilar.bat"` (usa o `csc.exe` do .NET Framework 4; só C# 5, sem interpolação de string `$""`). `cmd //c compilar.bat` pelo Git Bash não funciona.

## Segurança (estado em 06/11/2026)

- Pelo túnel só passam `/api/gps/owntracks` e `/api/health`; todo o resto (painel, API, estáticos) responde **403**. A requisição conta como externa se tiver `X-Forwarded-For`/`Forwarded`/`X-Real-IP`/`CF-Connecting-IP`, se o `Host` for o `NGROK_DOMAIN` ou se o IP de origem for público. Loopback e IPs privados (rede da loja) continuam liberados.
- Pela internet o `OWNTRACKS_TOKEN` é obrigatório (senha do HTTP Basic do OwnTracks ou header `X-Token`); sem ele o servidor responde 403 a posições externas.
- **Importante:** o waitress apaga cabeçalhos de proxy por padrão. `criar_servidor()` usa `clear_untrusted_proxy_headers=False`; sem isso o bloqueio não funciona em produção. O teste `test_waitress_repassa_cabecalho_do_tunel` protege isso.
- Validado em 06/11 com túnel ngrok real (domínio da conta: `unhasty-leighton-grouty.ngrok-free.dev`).
- **Ainda não há login de operador** (planejado para a semana 13).

## Dados e configuração no repositório

- **Decisão do André (11/11/2026):** o repositório é **público** e mesmo assim versiona `data/radar.db` (clientes reais da loja, com endereço e telefone), `.env`, `config/motoboys.json` e `tools/ngrok.exe`, para que um clone em qualquer PC funcione com os dados. Ele foi avisado de que os dados ficam públicos.
- Continuam fora do git: `data/*.db-wal`, `data/*.db-shm`, `data/ngrok.log`, `data/sessao.json`, `tools/cloudflared.exe` (68 MB, não usado pelo launcher), `Entrega_Professora/`, `_legado_local/`, `.venv/`, `scripts/docs/node_modules/`.
- **Nunca commitar segredos** no `.env`: nem o authtoken do ngrok (daria a qualquer um o domínio da loja e as posições dos motoboys) nem o `OWNTRACKS_TOKEN` real. O authtoken do ngrok fica no `ngrok.yml` de cada PC (`tools\ngrok.exe config add-authtoken ...`). O `OWNTRACKS_TOKEN` ainda está vazio no `.env` (11/11/2026), então o túnel não abre; falta decidir com o André onde guardar o token sem publicá-lo.
- Passo a passo para clonar em outro PC e sincronizar o banco: seção "Usar em outro PC" do README.
- Para commitar o banco, o GalviTracks deve estar fechado (ou fazer antes `PRAGMA wal_checkpoint(FULL)`), senão alterações recentes ficam só no `-wal`.
- **Nunca use `data/radar.db` em testes ou experimentos.** Para subir um servidor de teste isolado:
  ```bash
  PASTA_DADOS=<pasta temporária> DB_PATH=<pasta>/t.db ARQUIVO_SESSAO=<pasta>/s.json \
    .venv/Scripts/python run.py --no-browser --port 5099
  ```
  (variáveis de ambiente têm prioridade sobre o `.env`).

## Comandos

```bash
.venv/Scripts/python -m pytest -q          # testes (instale antes: pip install -r requirements-dev.txt)
.venv/Scripts/python run.py                # servidor em http://127.0.0.1:5000
.venv/Scripts/python scripts/simular_motoboy.py --todos
cd scripts/docs && npm install && npm run gerar   # regenera docs/Cronograma_Entregas_TCC.docx e docs/cronograma.md
```

- O `python` global não existe no PATH deste PC (abre a Microsoft Store); use sempre `.venv/Scripts/python`.
- No Windows teste com `http://127.0.0.1:PORTA`, **não** `localhost` (tenta IPv6 primeiro; cada conexão fica 0,2–2 s mais lenta).
- Testes: a fixture `cfg` em `tests/conftest.py` aponta tudo para `tmp_path` e zera `OWNTRACKS_TOKEN`/`NGROK_DOMAIN`; a rede é bloqueada (`requests.get` falha), o que também valida o modo offline. Em testes de IP público, não use faixas TEST-NET (198.51.100.0/24 etc.): o Python as considera `is_private`.
- CI: GitHub Actions em Ubuntu e Windows, Python 3.10, 3.12 e 3.13 (`.github/workflows/testes.yml`).

## Convenções

- Tudo em **português**: código, comentários, docs, commits.
- Commits no padrão Conventional Commits em português: `feat:`, `fix:`, `docs:`, `test:`, `perf:`, `style:`, `chore:`, `ci:`.
- Trabalhar em branch `feat/...` e fazer merge com `--no-ff` (`Merge branch 'feat/x': descrição`).
- **Só fazer push quando o André pedir.**
- O cronograma é gerado: edite `scripts/docs/dados.js` (e textos em `gerar.js`) e regenere; não edite `docs/cronograma.md` à mão.
- Ao mudar funcionalidade, atualizar README, `docs/` e `CHANGELOG.md` (seção `[Não lançado]`).

## Histórico recente

- **Até 02/10/2026**: semanas 1 a 9 (requisitos, arquitetura, GPS, rotas, v0.8.0, alertas).
- **06/11/2026, sessão anterior**: backend em tempo real (SSE, `/api/resumo`, sessão agrupada, WAL, saneamento de timestamps), painel novo em módulos ES com design system, `GalviTracks.exe` (substituiu `instalar.bat`/`iniciar.bat`).
- **06/11/2026, esta sessão**:
  1. Repositório renomeado para `GalviTracks` (referências, `pyproject.toml` → `galvitracks`, User-Agent do Nominatim `GalviTracks/0.8`).
  2. Cronograma replanejado: semanas 10–12 registradas como entregues (10 tempo real, 11 painel, 12 GalviTracks.exe), com observação de que foram publicadas em 06/11. **Confirmação de entrega por parada retirada do escopo** (trabalho futuro). Login passou para a semana 13. Milestones do GitHub ajustados: 10–12 fechados; issues #34–#36 fechadas como "not planned"; #38 concluída; #37 e #39 (indicadores por motoboy, Excel com indicadores) abertas **sem milestone**; #40–#42 (login, perfis, proteção da API) movidas para o milestone da semana 13.
  3. Segurança do túnel (merge `da5b4c5`): bloqueio do acesso externo, token obrigatório pela internet, exe e `tunel_ngrok.bat` não abrem túnel sem token, correção do waitress, 22 testes novos.

## Pendências e próximos passos (por prioridade)

1. **Login de operador (semana 13)**: versão enxuta, senha com hash no `.env` e sessão do Flask; perfis operador/gestor (#41) são opcionais. Issues #40–#42.
2. **Token do OwnTracks**: `NGROK_DOMAIN` já está no `.env`; falta o `OWNTRACKS_TOKEN` (sem publicá-lo no repositório público) e a mesma senha no OwnTracks dos celulares; depois testar um motoboy real com dados móveis. O exe já foi visto recusando o túnel com domínio preenchido e token vazio (11/11).
3. **Cronometragem de base (semana 14, 06/11)**: medir o tempo de planejamento de rotas no processo manual atual. Não depende do sistema; dá para começar já. Sugerido preparar planilha e protocolo de medição.
4. **Homologação na loja + release v0.9.0** (marco M3, data original 30/10 já passou; atualizar status/data quando acontecer). Lembrar de subir `__version__` e o selo do README.
5. Piloto com cronometragem (semana 15), questionário **SUS** (semana 16, meta ≥ 71), análise e artigo (17), **v1.0.0** e defesa (18, 04/12).
6. Menores: a seção "Situação atual" do `.docx` gerado cita 83 testes (atualizar no próximo `npm run gerar`); `send_bytes` do waitress gera DeprecationWarning nos testes.
