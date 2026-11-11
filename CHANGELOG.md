# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/). O projeto usa [versionamento semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Primeira execução em outro PC
- Banco da loja (`data/radar.db`), `.env`, `config/motoboys.json` e `tools/ngrok.exe` passam a ser versionados: um clone em qualquer PC abre com os dados.
- Senhas deste PC em `.env.local` (fora do git), com prioridade sobre o `.env`; lido pelo servidor, pelo `GalviTracks.exe` e pelo `tunel_ngrok.bat`.
- O `GalviTracks.exe` pergunta na primeira vez a senha do OwnTracks (mín. 6 caracteres, salva em `.env.local`) e o authtoken do ngrok (abre a página do token e roda `ngrok config add-authtoken`). As senhas aparecem como `*`; Enter pula e abre só o painel.
- README com a seção "Usar em outro PC". 3 testes novos (108 no total).

### Segurança do acesso pela internet
- Quem chega pelo túnel (cabeçalhos de proxy, domínio `NGROK_DOMAIN` ou IP público) só alcança `/api/gps/owntracks` e `/api/health`; painel, API e arquivos estáticos respondem 403. A rede local não muda.
- Pela internet o token do OwnTracks é obrigatório: sem `OWNTRACKS_TOKEN`, o servidor recusa as posições externas e o `GalviTracks.exe`/`tunel_ngrok.bat` não abrem o túnel.
- O waitress deixa de apagar o `X-Forwarded-For` (`clear_untrusted_proxy_headers=False`), que é como o servidor reconhece o acesso externo.
- Verificado com um túnel ngrok real; 22 testes novos, um deles com o waitress de verdade.

### Backend em tempo real, desempenho e robustez
- SSE em `/api/stream`: snapshot imediato, agrupamento de 250 ms, ping de 15 s, limite configurável/503 e polling preservado. Waitress com 24 threads configuráveis e envio de blocos pequenos.
- Estado com curso, precisão, horário de aceitação, online e versão por motoboy; velocidade suavizada por EMA, mantendo dados brutos no tracklog.
- Sessão GPS com flush em segundo plano a cada 5 s, gravação imediata de rota/status, tentativas contra bloqueios do OneDrive e flush no encerramento.
- SQLite WAL/NORMAL, conexões por thread, cache de clientes invalidado nas alterações e retenção diária da trilha (90 dias configuráveis).
- Saneamento de timestamps futuros/não numéricos, alertas no relógio do servidor, validação de coordenadas e proteção contra saltos no mesmo segundo.
- `/api/tracklog?simplificar=1` com Douglas-Peucker (~5 m), curso nos pontos e 404 para motoboy inexistente. Novo `/api/resumo` com frota, alertas, viagens e km GPS do dia.
- Histórico com início/fim Unix, duração e data de saída correta ao passar da meia-noite; migração de registros antigos. Falha SQL ao finalizar preserva a rota.
- Exportação Excel protege textos que começam como fórmulas.
- Simulador com curso/precisão variáveis, `--todos`, `--max-posicoes` e suporte a Tracker IDs personalizados via campo adicional `tid` em `/api/motoboys`.
- 40 testes novos (83 no total) e verificação real com Waitress, `curl -N`, 20 amostras de latência, frota simultânea, saturação de streams e heartbeat.
- Frontend mantido intacto para integração com a reforma paralela do painel; nenhuma dependência nova.

Planejado (ver [cronograma](docs/cronograma.md)): segurança do túnel, login de operador, homologação e avaliação em ambiente real. A confirmação de entrega por parada saiu do escopo (trabalho futuro).

### Adicionado (semana 9, 02/10/2026)
- Alertas de status no painel: **sem sinal** durante a entrega, **parado** fora de cliente e **bateria baixa** do celular.
- Endpoint `/api/alertas` e campos `alertas`, `bateria`, `carregando` e `recebido_em` em `/api/estado`.
- Bateria e indicador de alerta no ícone do motoboy e nas abas do painel.
- Simulador com cenários `--bateria`, `--parar-por` e `--cair-sinal`.
- Variáveis `ALERTA_*` no `.env` para ajustar os limites.
- 14 testes novos (43 no total).

## [0.8.0] - 2026-09-25 (entrega da semana 8)

### Adicionado
- Pacote `radar_tracker` em camadas (config, banco, frota, geo, roteamento, API, frontend).
- Filtro de leituras GPS por precisão, ordem temporal e saltos de velocidade. A velocidade informada pelo aparelho tem preferência.
- Token opcional no endpoint do OwnTracks (`OWNTRACKS_TOKEN`, via HTTP Basic ou `X-Token`).
- Identificação do motoboy pelo Tracker ID configurável em `config/motoboys.json`.
- Filtro de datas no histórico, que também vale para a exportação Excel.
- Replay de trilha com seleção de dia e traçado completo no mapa.
- Endpoints `/api/health` e `/api/motoboys`, e distância e origem (OSRM/offline) no cálculo de rota.
- Configuração por `.env`; scripts `instalar`/`iniciar` para Windows e Linux/macOS; servidor `waitress`.
- `scripts/seed_demo.py` (clientes fictícios) e `scripts/simular_motoboy.py` (simulador do OwnTracks).
- 29 testes automatizados e CI no GitHub Actions (Windows e Ubuntu).
- Documentação completa em `docs/` e cronograma de entregas em Word e Markdown.

### Corrigido
- Rota `/api/rm` registrada em duplicidade.
- Finalizar uma rota apagava nome e cor do motoboy da sessão.
- Nomes de clientes com aspas quebravam o painel (injeção de HTML).
- Termo de busca de endereço não era codificado na URL.
- Filtro de datas do relatório não tinha efeito.
- Leituras de GPS no mesmo segundo eram descartadas.

### Alterado
- Exportação Excel usa `openpyxl` diretamente (sem `pandas`).
- Leaflet atualizado para 1.9.4.
- Binários, bancos de dados e domínio do ngrok removidos do repositório.

## [0.1.0] - 2026-01-28 (protótipo V79)

### Adicionado
- Protótipo monolítico (`app_radar_pro.py`) em uso na Radar Auto Peças: rastreamento via OwnTracks, rotas OSRM com fallback, vizinho mais próximo, clientes, histórico com nota, replay e Excel.
