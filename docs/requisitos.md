# Requisitos do sistema

Requisitos levantados pela Galvitech Ltda com a equipe da Radar Auto Peças, a partir do processo de despacho de motoboys da loja. A coluna **Status** mostra o que já existe na versão 0.8.0.

## Atores

| Ator | Descrição |
|------|-----------|
| **Operador de expedição** | Monta as rotas, informa a nota fiscal e acompanha os motoboys pelo painel web. |
| **Motoboy** | Faz as entregas com o app OwnTracks instalado no celular, que envia a posição GPS. |
| **Gestor** | Consulta o histórico, exporta relatórios e revê trajetos (replay). |

## Requisitos funcionais

| ID | Requisito | Área | Status |
|----|-----------|-----------|--------|
| RF01 | Exibir no mapa a posição atual de todos os motoboys, atualizada a cada 2 s. | Rastreamento | ✅ |
| RF02 | Receber posições GPS enviadas pelo app OwnTracks (modo HTTP). | Rastreamento | ✅ |
| RF03 | Mostrar a velocidade instantânea de cada motoboy. | Rastreamento | ✅ |
| RF04 | Descartar leituras de GPS imprecisas ou incoerentes (saltos, fora de ordem). | Rastreamento | ✅ |
| RF05 | Montar a rota de cada motoboy adicionando paradas (clientes cadastrados, busca de endereço ou clique no mapa). | Rotas | ✅ |
| RF06 | Calcular trajeto e tempo estimado do circuito loja → paradas → loja. | Rotas | ✅ |
| RF07 | Otimizar a ordem das paradas (heurística do vizinho mais próximo). | Rotas | ✅ |
| RF08 | Estimar o tempo mesmo sem acesso ao serviço de roteirização (modo offline). | Rotas | ✅ |
| RF09 | Exigir o número da nota fiscal/pedido para iniciar uma entrega. | Histórico | ✅ |
| RF10 | Bloquear a edição da rota enquanto o motoboy estiver em entrega. | Rotas | ✅ |
| RF11 | Cadastrar, editar, colorir e excluir clientes com geolocalização. | Clientes | ✅ |
| RF12 | Registrar cada viagem (motoboy, data, saída, chegada, destinos, nota). | Histórico | ✅ |
| RF13 | Filtrar o histórico por período e exportar em Excel. | Histórico | ✅ |
| RF14 | Reproduzir (replay) a trilha percorrida por um motoboy em um dia. | Replay | ✅ |
| RF15 | Alertar quando um motoboy perder o sinal, ficar parado por muito tempo fora de um cliente ou estiver com bateria baixa no celular. | Rastreamento | ✅ semana 9 |
| RF16 | Confirmar a entrega em cada parada, registrando o horário de chegada ao cliente. | Histórico | 🔜 semana 10 |
| RF17 | Painel de indicadores (entregas por motoboy, tempo médio de rota, km rodados). | Relatórios | 🔜 semana 11 |
| RF18 | Acesso ao painel com login de operador e perfis (operador / gestor). | Segurança | 🔜 semana 12 |

**Fora do escopo:** integração com outros sistemas de gestão da loja. O sistema é independente: os clientes são cadastrados nele e o número da nota é informado manualmente pelo operador.

## Requisitos não funcionais

| ID | Requisito | Como é atendido |
|----|-----------|-----------------|
| RNF01 | **Custo zero de licenciamento.** | Somente software livre: Flask, SQLite, Leaflet, OpenStreetMap, OSRM, OwnTracks. |
| RNF02 | **Portabilidade**: rodar em qualquer PC Windows, Linux ou macOS com Python 3.10+. | Scripts `instalar`/`iniciar` para cada sistema; CI testa Windows e Ubuntu. |
| RNF03 | **Tempo real**: atualização do mapa em até 2 s. | Consulta periódica (`/api/estado`) a cada 2 s. |
| RNF04 | **Resiliência**: continuar operando se OSRM/Nominatim estiverem fora do ar. | Fallback offline (distância Haversine + velocidade média + tempo por parada). |
| RNF05 | **Persistência**: não perder rotas em andamento se o servidor reiniciar. | Estado da frota gravado de forma atômica em `data/sessao.json`. |
| RNF06 | **Usabilidade**: escore SUS na faixa "boa" (≥ 71) ou superior. | Avaliação planejada nas semanas 14–16. |
| RNF07 | **Responsividade**: uso no celular do operador. | Painel recolhível em telas ≤ 768 px. |
| RNF08 | **Segurança**: endpoint de GPS não pode aceitar posições de qualquer origem. | Token (`OWNTRACKS_TOKEN`) via HTTP Basic/X-Token, obrigatório para acesso pela internet; pelo túnel só o endpoint de GPS é acessível; saída de HTML escapada no frontend. |
| RNF09 | **Privacidade**: dados de clientes não vão para o repositório público. | Banco e configuração local no `.gitignore`; exemplos com dados fictícios. |
| RNF10 | **Manutenibilidade**: código modular e testado. | Pacote em camadas, 43 testes automatizados, integração contínua. |
| RNF11 | **Alertas sem falso positivo óbvio**: não alertar parada no cliente, na loja ou quando o celular está carregando. | Raio de cliente/loja, campo `bs` do OwnTracks e supressão de "parado" quando já está sem sinal. |

## Regras de negócio

- **RN01**: o motoboy só pode sair para a entrega com pelo menos uma parada **e** o número da nota/pedido informado.
- **RN02**: durante a entrega (status `EM_ROTA`) as paradas não podem ser alteradas.
- **RN03**: ao finalizar a rota, a viagem é gravada no histórico e o motoboy volta a `LIVRE`.
- **RN04**: toda rota começa e termina na loja (coordenadas `BASE_LAT`/`BASE_LON`).
- **RN05**: o tempo do OSRM é multiplicado por `FATOR_ATRASO` (1,6 por padrão) para refletir trânsito urbano, estacionamento e atendimento no balcão do cliente.
- **RN06**: clientes são únicos pelo nome (sem diferenciar maiúsculas de minúsculas).
