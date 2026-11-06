# Histórico de desenvolvimento

Este documento registra como o sistema evoluiu, as decisões tomadas em cada etapa e os problemas encontrados. Ele complementa o [cronograma](cronograma.md).

## Metodologia

O projeto segue a **Design Science Research** (Hevner et al., 2004), em ciclos de construção e avaliação do artefato:

1. **Relevância**: problema real observado na Radar Auto Peças, onde o despacho de motoboys era manual, sem rastreamento nem histórico.
2. **Rigor**: base em trabalhos correlatos (otimização de rotas, pilha OpenStreetMap/Leaflet, tratamento de GPS) e em soluções de mercado (Vuupt, Loggi, Foody Delivery).
3. **Design**: implementação incremental, com entregas semanais às sextas-feiras.
4. **Avaliação**: cronometragem do planejamento de rotas (antes/depois) e questionário SUS.

## Fase 1: protótipo na loja (jan/2026)

A primeira versão foi um script único (`app_radar_pro.py`, "V79") usado diretamente no balcão da Radar Auto Peças. Ela validou a viabilidade da pilha aberta:

- recebimento das posições do **OwnTracks** via HTTP;
- mapa **Leaflet** com os motoboys e os clientes;
- rota pelo **OSRM** com *fallback* matemático;
- otimização por **vizinho mais próximo**;
- histórico com número da nota, replay e exportação Excel.

O protótipo está preservado no histórico do Git (commit `feat: adiciona protótipo funcional V79`) como linha de base da refatoração.

### Problemas identificados no protótipo

| Problema | Impacto |
|----------|---------|
| Arquivo único de 650 linhas misturando HTML, CSS, JS, SQL e regras | Difícil manter e testar. |
| Rota `/api/rm` registrada duas vezes | Código morto e ambiguidade. |
| Finalizar a rota sobrescrevia o estado do motoboy sem `nome`/`cor` | Sessão corrompida após a primeira entrega. |
| Nomes de clientes interpolados em `innerHTML` e `onclick` | Nomes com apóstrofo (ex.: *D'Ávila*) quebravam o painel; risco de XSS. |
| Termo de busca sem `encodeURIComponent` | Endereços com `&` ou `#` falhavam. |
| Filtro de datas do relatório sem efeito | Relatório sempre com todo o histórico. |
| Motoboys fixos em três lugares do código | Trocar um motoboy exigia editar o código. |
| Domínio do ngrok, bancos e executáveis (100 MB) versionados | Repositório pesado e dados reais expostos. |
| Nenhum teste automatizado | Regressões só apareciam em produção. |

## Fase 2: refatoração e robustez (set/2026, versão 0.8.0)

### Refatoração modular

O código foi separado em camadas (ver [arquitetura](arquitetura.md)): configuração, banco, frota, geografia, roteamento, API e frontend. A API manteve **as mesmas URLs** do protótipo, então os celulares já configurados continuam funcionando sem alteração.

### Tratamento de dados de GPS

Seguindo Borges et al. (2023), que mostram que dados brutos de GPS precisam de limpeza, cada leitura agora passa por um filtro:

- **precisão** (`acc`) pior que 100 m → descartada;
- **timestamp** anterior ao último aceito → descartada; timestamp igual é aceito (o OwnTracks tem resolução de 1 s);
- **salto** que implicaria mais de 150 km/h → descartado;
- **velocidade** informada pelo aparelho (`vel`) tem preferência sobre a calculada.

O simulador expôs um caso real durante os testes: duas leituras no mesmo segundo eram rejeitadas, e o problema foi corrigido.

### Segurança e privacidade

- Token opcional no endpoint de GPS (`OWNTRACKS_TOKEN`), comparado em tempo constante (`hmac.compare_digest`).
- Todo texto vindo do banco é inserido no DOM com `textContent` ou escapado (`esc()`).
- Banco com clientes reais, sessão, `.env` e executáveis fora do Git.

### Portabilidade

- Windows: `GalviTracks.exe` (fonte em `scripts/windows/launcher/`) cria o ambiente virtual, abre o túnel e sobe o servidor num clique; um *job object* garante que o servidor e o túnel fechem junto com a janela. Linux/macOS: `instalar.sh` e `iniciar.sh`.
- Servidor **waitress** (compatível com Windows) em vez do servidor de desenvolvimento do Flask.
- `pandas` removido: a exportação usa `openpyxl` diretamente, o que torna a instalação menor e mais rápida.

### Qualidade

- **29 testes** com `pytest`, sem acesso à rede. Os testes forçam o OSRM "fora do ar", o que valida o fallback.
- **GitHub Actions** roda a suíte em Windows e Ubuntu, Python 3.10, 3.12 e 3.13.
- Commits no padrão *Conventional Commits* (`feat`, `fix`, `refactor`, `test`, `docs`, `build`, `chore`).

## Fase 3: entregas semanais (out/2026)

### Semana 9 (02/10): alertas de status

O ponto fraco de rastrear pelo celular do motoboy é que o aparelho pode desligar, ficar sem internet ou ter o GPS desativado, e o operador só percebe quando liga para o motoboy. A semana 9 transformou isso em **alertas automáticos no painel**:

- **Sem sinal** (crítico): durante a entrega, nenhuma mensagem do celular há 3 min. Considera também quem nunca enviou posição desde a saída.
- **Parado fora de cliente** (alerta): mais de 10 min dentro de um raio de 50 m, longe de clientes, paradas da rota e da loja.
- **Bateria baixa** (aviso): bateria do celular abaixo de 20%, usando o campo `batt` que o OwnTracks já envia. É ignorado quando o celular está carregando.

Decisões:

- As regras ficam em `alertas.py` como **funções puras** (recebem o estado e a hora atual), o que permitiu testar cada cenário sem esperar minutos reais.
- O tempo "parado" usa um **ponto de referência com raio** em vez da velocidade instantânea, que oscila com o ruído do GPS mesmo com a moto parada.
- O **último contato** é registrado mesmo quando a posição é descartada pelo filtro de GPS: uma leitura imprecisa ainda prova que o celular está conectado.
- O teste ponta a ponta com o simulador revelou um alerta duplicado: sem sinal, a última posição fica "congelada" e o motoboy também aparecia como parado. O alerta de parada passou a ser suprimido nesse caso.
- Os limites ficam no `.env`, para ajustar à realidade da loja depois do piloto.

## Próximas fases

Veja o [cronograma](cronograma.md): confirmação de entrega por parada, indicadores, login de operador, homologação, avaliação em ambiente real (cronometragem + SUS) e redação final do TCC.

## Como contribuir / padrão de trabalho

1. Crie um branch a partir de `main` (`feat/nome-da-funcionalidade`).
2. Escreva ou atualize os testes em `tests/`.
3. Rode `pytest` antes de cada commit.
4. Use mensagens no padrão `tipo: descrição no imperativo`.
5. Abra um Pull Request. O CI precisa passar antes do merge.
