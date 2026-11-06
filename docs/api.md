# Referência da API REST

Base: `http://<servidor>:5000`. Todas as requisições `POST` usam `Content-Type: application/json`.
Erros de validação retornam **400** `{"ok": 0, "erro": "..."}` e motoboy inexistente retorna **404**.

## Sistema

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/` | Painel web. |
| GET | `/api/health` | `{"status": "ok"}`, usado para monitoramento. |
| GET | `/api/motoboys` | Lista `[{id, nome, cor, tid}]` configurada em `config/motoboys.json`. `tid` foi acrescentado para o simulador reconhecer IDs personalizados. |

## Frota e rotas

| Método | Rota | Corpo | Resposta |
|--------|------|-------|----------|
| GET | `/api/estado` | — | Objeto indexado pelo id do motoboy: `status`, `rota[]`, `nota`, `hora_saida`, `lat_atual`, `lon_atual`, `velocidade`, `last_ts`, `bateria`, `carregando`, `recebido_em`, `inicio_ts`, `parado_desde`, `nome`, `cor` e `alertas[]` (ver abaixo). |
| POST | `/api/add` | `{id, nome, lat, lon}` | `{ok}`: adiciona parada (só com status `LIVRE`). |
| POST | `/api/rm` | `{id, idx}` | `{ok}`: remove a parada da posição `idx`. |
| POST | `/api/otimizar` | `{id}` | `{ok}`: reordena as paradas pelo vizinho mais próximo (mínimo de 2). |
| POST | `/api/start` | `{id, nota}` | `{ok}`: inicia a entrega (exige paradas e nota). |
| POST | `/api/end` | `{id}` | `{ok}`: finaliza e grava no histórico. |
| POST | `/api/calc` | `{stops: [{lat, lon}]}` | `{pontos: [[lat, lon]], minutos, distancia_km, fonte: "osrm" \| "offline"}` |
| GET | `/api/buscar?q=texto` | — | Resultado do Nominatim (lista), limitado à `CIDADE_BUSCA`. |

### Estado ampliado e SSE

Os campos antigos de `/api/estado` são preservados. Cada motoboy inclui também:

| Campo | Significado |
|-------|-------------|
| `curso` | Direção em graus, norte=0, leste=90, intervalo [0, 360); `null` antes de ser conhecida. Usa `cog` ou o rumo entre posições aceitas com deslocamento >10 m. |
| `ts_posicao` | Timestamp Unix em segundos, relógio do servidor, da última posição aceita; 0 antes da primeira. |
| `precisao` | `acc` da última posição aceita, em metros; `null` se ausente. |
| `online` | `true` se existe contato do celular há menos de `ALERTA_SEM_SINAL_MIN` minutos, inclusive fora de entrega. |
| `versao` | Contador inteiro de mudanças daquele motoboy, incluindo contato/bateria, GPS aceito, edição de rota/status e transições de `online`/alertas observadas ao avaliar o snapshot. |

`velocidade` no snapshot é suavizada por EMA: `alpha × leitura + (1-alpha) × anterior`, com `GPS_VELOCIDADE_ALPHA=0.35`. A trilha continua com velocidade bruta. `recebido_em`, `inicio_ts`, `parado_desde` e `ts_posicao` usam o relógio do servidor; `last_ts` é o horário saneado do GPS.

`GET /api/stream` mantém conexão **Server-Sent Events**, com cabeçalhos:

```http
Content-Type: text/event-stream
Cache-Control: no-cache
X-Accel-Buffering: no
```

O início é enviado imediatamente, com `retry: 3000` e um evento `estado` contendo **o mesmo snapshot completo de `/api/estado`** (todos os campos e todos os motoboys):

```text
retry: 3000
event: estado
data: {"0":{"status":"LIVRE","rota":[],"curso":null,"online":false,"versao":0,...}}

```

As reticências acima apenas abreviam a documentação; o JSON transmitido é completo e válido. Cada mudança publica uma nova revisão; mudanças rápidas são agrupadas com intervalo mínimo de 250 ms entre eventos (aproximadamente 4/s). A espera usa `threading.Condition`, sem varrer o estado em loop. Sem mudanças, envia `: ping` a cada 15 s. Nesse prazo também reavalia `online` e alertas dependentes do tempo: se o snapshot mudou, envia `estado` em vez de ping.

Limite padrão: `STREAM_MAX=10`. Conexões excedentes recebem **503**, JSON de erro e `Retry-After: 3`; o frontend pode consultar `/api/estado` a cada 2 s como fallback. O gerador libera a vaga no fechamento; o Waitress identifica desconexões com `channel_request_lookahead=1`, e um stream ocioso é liberado até a próxima mudança/heartbeat (até 15 s). O encerramento do servidor acorda todas as esperas.

O backend preserva a API do painel antigo. A adoção de `EventSource` e o fallback no frontend são responsabilidade da reforma paralela de `templates/` e `static/`.

### Resumo do dia

`GET /api/resumo`:

```json
{"em_rota":1,"livres":3,"com_alerta":1,"entregas_hoje":4,"km_hoje":12.375}
```

`com_alerta` conta motoboys com ao menos um alerta. `entregas_hoje` conta viagens finalizadas cuja **data de saída** é hoje. `km_hoje` soma Haversine entre pontos consecutivos do dia local, separadamente por motoboy; não conecta o último ponto de um motoboy ao primeiro de outro e não inclui segmento iniciado no dia anterior. É distância GPS observada, não a distância planejada no OSRM.

## Alertas

Cada motoboy em `/api/estado` traz a lista `alertas`, e `GET /api/alertas` devolve os alertas de toda a frota, do mais grave ao mais leve:

```json
[
  { "tipo": "sem_sinal", "nivel": "critico", "mensagem": "Sem sinal há 4 min", "minutos": 4, "moto_id": 0, "motoboy": "Motoboy Um" },
  { "tipo": "parado", "nivel": "alerta", "mensagem": "Parado há 12 min fora de um cliente", "minutos": 12, "moto_id": 1, "motoboy": "Motoboy Dois" },
  { "tipo": "bateria_baixa", "nivel": "aviso", "mensagem": "Bateria do celular em 14%", "bateria": 14, "moto_id": 2, "motoboy": "Motoboy Três" }
]
```

| Tipo | Nível | Regra (padrões configuráveis no `.env`) |
|------|-------|------------------------------------------|
| `sem_sinal` | crítico | Em entrega e sem mensagem do celular há `ALERTA_SEM_SINAL_MIN` (3 min), contando desde a saída se nunca enviou. |
| `parado` | alerta | Em entrega, sem sair de um raio de `ALERTA_RAIO_PARADO_M` (50 m) há `ALERTA_PARADO_MIN` (10 min) e a mais de `ALERTA_RAIO_CLIENTE_M` (100 m) de clientes, paradas e loja. Não aparece junto com `sem_sinal`. |
| `bateria_baixa` | aviso | `batt` abaixo de `ALERTA_BATERIA_MIN` (20%) e celular fora da tomada. Vale mesmo fora da entrega. |

## GPS (OwnTracks)

`POST /api/gps/owntracks`: recebe o [payload de localização do OwnTracks](https://owntracks.org/booklet/tech/json/#_typelocation).

```json
{ "_type": "location", "tid": "0", "lat": -26.5085, "lon": -49.1054, "tst": 1790364807, "acc": 8, "vel": 32 }
```

| Campo | Uso |
|-------|-----|
| `tid` | Tracker ID → identifica o motoboy (campo `tid` em `config/motoboys.json`). |
| `lat`, `lon` | Posição. |
| `tst` | Timestamp Unix da leitura. Ausente, inválido, não finito, não positivo ou >5 min à frente: usa a hora do servidor. Na carga da sessão, `last_ts` futuro é zerado. Leituras antigas continuam sujeitas ao filtro de ordem. |
| `acc` | Precisão em metros. Leituras acima de `GPS_PRECISAO_MAX_M` são descartadas. |
| `vel` | Velocidade em km/h informada pelo aparelho (preferida quando presente). |
| `cog` | Direção em graus; se ausente/inválida, calcula o rumo quando o deslocamento aceito supera 10 m. Sem deslocamento suficiente, mantém o último curso. |
| `batt` | Bateria do celular em % (alerta de bateria baixa). |
| `bs` | Estado da bateria: `1` desconectado, `2` carregando, `3` carga completa. Com 2 ou 3 o alerta de bateria é ignorado. |

Resposta sempre `[]` (o OwnTracks espera uma lista). Se `OWNTRACKS_TOKEN` estiver definido, envie-o como **senha** do HTTP Basic Auth (o usuário pode ser qualquer um) ou no header `X-Token`. Sem o token, a resposta é **401**.

**Acesso pela internet.** Requisições que chegam por túnel ou proxy (cabeçalho `X-Forwarded-For`, `Forwarded`, `X-Real-IP` ou `CF-Connecting-IP`), com o `Host` igual a `NGROK_DOMAIN` ou de um IP público só podem usar `/api/gps/owntracks` e `/api/health`; as demais rotas, incluindo o painel e os arquivos estáticos, respondem **403**. Nesse caso o token é obrigatório: com `OWNTRACKS_TOKEN` vazio, o endpoint responde **403** a quem vem de fora. Requisições da própria máquina e da rede local (IPs privados) não mudam.

JSON não objeto, coordenadas não finitas/fora de latitude [-90,90] e longitude [-180,180] são ignorados sem erro 500. Saltos impossíveis também são filtrados entre leituras do mesmo segundo. Contato/bateria continuam atualizados quando uma posição é descartada por precisão ou ordem temporal.

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/tracklog?id=0[&data=AAAA-MM-DD][&simplificar=1]` | Pontos `[{lat, lon, velocidade, timestamp, curso}]` do dia informado ou das últimas 24 h. Motoboy inexistente: 404; ID/data inválidos: 400. |

Sem `simplificar=1`, retorna todos os pontos como antes, acrescentando `curso` (`null` nos pontos antigos). Com o parâmetro, aplica Douglas-Peucker em projeção local, tolerância de aproximadamente 5 m, preservando primeiro/último ponto, curvas relevantes e metadados dos pontos mantidos. A simplificação não altera os dados gravados. A trilha tem retenção configurável por `TRACKLOG_DIAS` (padrão 90).

## Clientes

| Método | Rota | Corpo | Resposta |
|--------|------|-------|----------|
| GET | `/api/clientes` | — | `[{id, nome, lat, lon, cor, telefone, obs}]` em ordem alfabética. |
| POST | `/api/save_cli` | `{nome, lat, lon}` | `{ok, id}`. Se já existir um cliente com o mesmo nome, devolve o id existente. |
| POST | `/api/update_client` | `{id, nome, telefone}` | `{ok}` |
| POST | `/api/update_color` | `{id, cor: "#rrggbb"}` | `{ok}` |
| POST | `/api/apagar_cliente` | `{id}` | `{ok}` |

## Histórico e relatórios

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/get_historico[?inicio=AAAA-MM-DD&fim=AAAA-MM-DD]` | Viagens (mais recentes primeiro). |
| GET | `/baixar_excel[?inicio=...&fim=...]` | Planilha `.xlsx` com o mesmo filtro. |

O histórico inclui também `inicio_ts`, `fim_ts` (Unix, segundos) e `duracao_min`. A data da viagem é a data da saída mesmo quando termina após a meia-noite. Registros antigos são migrados a partir dos horários existentes; quando a chegada é menor que a saída, assume o dia seguinte. Textos no Excel iniciados por `=`, `+`, `-` ou `@` recebem apóstrofo para impedir interpretação como fórmula. Uma falha SQL ao finalizar mantém a rota em andamento para permitir nova tentativa.

## Verificação real do SSE

```bash
python scripts/verificar_stream.py
```

Esse comando usa Waitress com a mesma configuração de `run.py`, `curl -N`, banco temporário e `simular_motoboy.py --todos`. Mede 20 POSTs (limite de 300 ms), valida 503 com vagas ocupadas, envio contínuo da frota e ping de 15 s. Não altera os dados da loja e força roteamento offline. Requer `curl` no PATH.

Para conferir manualmente com o servidor e rotas já montadas, em terminais separados:

```bash
python run.py --no-browser
curl -N http://127.0.0.1:5000/api/stream
python scripts/simular_motoboy.py --todos --token SUA_SENHA
```

O simulador aceita `--max-posicoes 25` para uma execução curta; `--todos` usa o `tid` real de cada motoboy e uma thread/conexão HTTP por motoboy.

## Exemplo com `curl`

```bash
curl -X POST localhost:5000/api/add -H "Content-Type: application/json" \
     -d '{"id":0,"nome":"Oficina Centro","lat":-26.4851,"lon":-49.0713}'
curl -X POST localhost:5000/api/start -H "Content-Type: application/json" -d '{"id":0,"nota":"NF-1001"}'
curl -X POST localhost:5000/api/gps/owntracks -H "Content-Type: application/json" \
     -d '{"_type":"location","tid":"0","lat":-26.50,"lon":-49.10,"acc":10}'
curl -X POST localhost:5000/api/end -H "Content-Type: application/json" -d '{"id":0}'
```
