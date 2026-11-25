# Protocolo de avaliação do GalviTracks

Avaliação em ambiente real na Radar Auto Peças, etapa 4 da Design Science Research do TCC. Responde à pergunta de pesquisa: *em que medida o sistema reduz o tempo de planejamento de rotas e aumenta a eficiência e a rastreabilidade das entregas?*

| Arquivo | Para que serve |
|---|---|
| [`Planilha_Avaliacao_GalviTracks.xlsx`](Planilha_Avaliacao_GalviTracks.xlsx) | Medições da base e do piloto, respostas do SUS, percepção dos motoboys, incidentes e resumo calculado |
| [`Questionario_SUS.pdf`](Questionario_SUS.pdf) | Questionário SUS pronto para imprimir (1 página por pessoa) |
| [`../../scripts/docs/gerar_avaliacao.py`](../../scripts/docs/gerar_avaliacao.py) | Gera a planilha em branco de novo, se precisar |

Na planilha, **amarelo = preencher**; o resto é fórmula. A aba *Leia-me* tem um exemplo de linha preenchida e a aba *Resumo* mostra médias, medianas, redução percentual e a nota SUS automaticamente.

## 1. O que se mede

| Variável | Definição | Onde |
|---|---|---|
| **Tempo de planejamento do despacho** (variável principal) | Do momento em que o operador começa a organizar a saída (pedidos/notas em mãos) até o motoboy ser liberado com a ordem das paradas definida. | Abas *Base* e *Piloto* |
| Nº de paradas | Quantos clientes o motoboy vai visitar nessa saída. Permite comparar o tempo **por parada**, já que despachos maiores demoram mais. | Abas *Base* e *Piloto* |
| Rastreabilidade | No piloto, cada saída fica no histórico com motoboy, horários, destinos e nº da nota (o sistema exige a nota). Na base, anotar se a nota foi registrada em algum lugar. | Coluna *Observações* e histórico do sistema |
| Usabilidade | Questionário SUS (Brooke, 1996), nota de 0 a 100. Meta do TCC: ≥ 71 (*bom*, Bangor et al., 2009). | Abas *SUS respostas* e *SUS formulário* |
| Percepção dos motoboys (opcional) | 4 afirmações sobre o OwnTracks e a rota, de 1 a 5. | Aba *Motoboys* |
| Incidentes | Falhas e imprevistos durante o piloto. | Aba *Incidentes* |

**Quando o cronômetro começa e para:**
- **Base (sem sistema):** começa quando o operador pega os pedidos para montar a saída; para quando o motoboy sai sabendo a ordem das entregas (por telefone, WhatsApp, papel ou de cabeça).
- **Piloto (com sistema):** começa quando o operador começa a montar a rota no painel (buscar o primeiro cliente); para no clique em **Sair para entrega**.

Use o cronômetro do celular e anote **minutos** e **segundos** separados. Quem cronometra deve ser sempre a mesma pessoa, de preferência alguém que não seja o operador.

## 2. Cronograma proposto (reta final)

| Quando | Atividade |
|---|---|
| Qui 26/11 e sex 27/11 | **Base:** cronometrar pelo menos 20 despachos do jeito atual. **Homologação:** conferir o sistema com o operador de expedição (lista da seção 4). |
| Sex 27/11 (fim do dia) | **Treinamento** (seção 3) e configuração do OwnTracks nos celulares. Release **v0.9.0**. |
| Seg 30/11 a qua 02/12 | **Piloto:** operação real com o sistema, cronometrando pelo menos 20 despachos e anotando incidentes. |
| Qua 02/12 (fim do dia) | **SUS** com os usuários do painel e percepção dos motoboys. |
| Qui 03/12 | Análise e resultados no artigo. |
| Sex 04/12 | Defesa (**v1.0.0**). |

Se a loja trabalhar no sábado 28/11, use o dia para completar a base. Com menos de 20 despachos em alguma fase, o trabalho segue, mas registre isso como limitação.

## 3. Treinamento (cerca de 30 minutos)

**Operadores e gestor (20 min, no painel):**
1. Entrar com o usuário e senha de cada um (o gestor cria em *menu do usuário → Usuários*).
2. Ver a frota no mapa: cores, status, bateria, *sem sinal*.
3. Montar uma rota: buscar o cliente (ou clicar no pino), ordenar com **Otimizar ordem**, conferir tempo e distância.
4. Digitar o nº da nota e clicar em **Sair para entrega**; acompanhar; **Finalizar rota** quando o motoboy voltar.
5. Cadastrar uma oficina nova (*Novo cliente no mapa*), abrir o histórico e exportar o Excel.
6. Onde aparecem os alertas (sino) e o que fazer.

**Motoboys (10 min por celular):**
1. Instalar o OwnTracks e configurar o modo HTTP com o endereço do servidor, o usuário/senha e o Tracker ID do motoboy (passo a passo em [`../instalacao.md`](../instalacao.md#4-configurar-o-owntracks-no-celular-do-motoboy)).
2. Liberar localização "sempre" e tirar o app da economia de bateria.
3. Fazer uma volta no quarteirão e conferir no painel.

## 4. Homologação (antes do piloto)

Marque com o operador de expedição:

- [ ] Login de cada usuário funciona; o operador não vê *Usuários*.
- [ ] Os 4 motoboys aparecem no mapa com posição real pelo celular (via túnel).
- [ ] Rota com 3+ paradas: cálculo, otimização e tempo estimado coerentes.
- [ ] *Sair para entrega* exige a nota e grava no histórico ao finalizar.
- [ ] Alertas: sem sinal, parado e bateria baixa aparecem (o simulador ajuda a testar).
- [ ] Histórico com filtro de datas e exportação Excel.
- [ ] Fechar e abrir o GalviTracks não perde a rota em andamento.

Com tudo marcado, publicar a **v0.9.0** (homologada).

## 5. Ética e cuidados

- Participação voluntária; explique o objetivo e peça o consentimento verbal (ou escrito, se o curso exigir).
- Na planilha e no artigo, use iniciais ou códigos (R01, M01), nunca nomes completos nem dados de clientes.
- O rastreamento acontece só durante o expediente e as entregas; combine isso com os motoboys.

## 6. Análise

- **Descritiva** (automática na aba *Resumo*): número de despachos, média, mediana, desvio padrão, mínimo e máximo em cada fase, tempo por parada e **redução percentual** (base − piloto) ÷ base.
- **Comparação estatística:** com as duas amostras independentes e pequenas, usar o teste de **Mann-Whitney** (não paramétrico) sobre os tempos por despacho e por parada; considerar significativo com p < 0,05. Com os dados digitados, o cálculo pode ser feito em Python (`scipy.stats.mannwhitneyu`).
- **SUS:** média, mínimo e máximo; classificação pelas faixas de Bangor, Kortum e Miller (2009); comparar com a meta ≥ 71.
- **Discussão:** incidentes, efeito do aprendizado nos primeiros dias, amostra pequena e período curto (limitações).

## Referências

- BANGOR, A.; KORTUM, P.; MILLER, J. Determining what individual SUS scores mean: adding an adjective rating scale. *Journal of Usability Studies*, v. 4, n. 3, p. 114–123, 2009.
- BROOKE, J. SUS: a quick and dirty usability scale. In: *Usability Evaluation in Industry*. London: Taylor & Francis, 1996. p. 189–194.
