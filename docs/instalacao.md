# Instalação e implantação

## Pré-requisitos

- **Python 3.10 ou superior** ([python.org](https://www.python.org/downloads/)). No Windows, marque **"Add python.exe to PATH"** durante a instalação.
- **Git** (opcional, para clonar), ou baixe o ZIP pelo botão *Code → Download ZIP* do GitHub.
- Internet para os mapas (tiles do OpenStreetMap) e para o cálculo de rotas. Sem internet, o sistema continua funcionando com estimativa offline de tempo, mas o mapa de fundo não carrega.

## 1. Rodar localmente (qualquer PC)

### Windows

Dê dois cliques em **`GalviTracks.exe`**, na raiz do projeto. Na primeira execução ele cria o ambiente virtual (`.venv`) e instala as dependências. Nas próximas, só reinstala as dependências quando o `requirements.txt` mudar.

O repositório já traz o banco da loja (`data/radar.db`, com os clientes), o `.env`, o `config/motoboys.json` e o `tools/ngrok.exe`, então um clone em outro PC abre com os mesmos dados. Se algum deles faltar, o launcher copia `.env.example` → `.env` e `config/motoboys.example.json` → `config/motoboys.json`, e cadastra clientes de demonstração quando o banco está vazio.

**Em um PC novo**, o `GalviTracks.exe` pergunta na primeira vez as duas senhas que **não** vão para o repositório público: a senha dos celulares (`OWNTRACKS_TOKEN`, salva em `.env.local`, que fica fora do git) e o authtoken do ngrok (salvo na configuração do ngrok do PC; o exe abre [a página do token](https://dashboard.ngrok.com/get-started/your-authtoken)). Enter sem digitar pula a pergunta e abre só o painel. O `.env.local` tem prioridade sobre o `.env` e também é lido pelo `tunel_ngrok.bat`.

**Levar as alterações do banco para o GitHub:** feche o GalviTracks (assim tudo é gravado no `radar.db`) e faça commit e push do `data/radar.db`. Evite usar o sistema em dois PCs ao mesmo tempo: cada um teria um banco diferente e o git não consegue juntar os dois.

Em seguida abre o túnel ngrok (passo 3 abaixo), sobe o servidor e abre o painel. Fechar a janela encerra o servidor e o túnel.

Opções de linha de comando: `GalviTracks.exe --sem-tunel` (não abre o ngrok) e `--sem-navegador`.

O executável é compilado de [`scripts/windows/launcher/GalviTracks.cs`](../scripts/windows/launcher/GalviTracks.cs) por `scripts\windows\launcher\compilar.bat`, que usa o compilador C# já incluído no Windows.

### Linux / macOS

```bash
git clone https://github.com/AndreeSpecht/GalviTracks.git
cd GalviTracks
./instalar.sh
./iniciar.sh
```

### Manual (qualquer sistema)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    |    Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                              # Windows: copy .env.example .env
cp config/motoboys.example.json config/motoboys.json
python scripts/seed_demo.py                       # clientes fictícios (opcional)
python run.py
```

O painel abre em **http://127.0.0.1:5000**. Outras máquinas da mesma rede acessam por `http://<IP-do-servidor>:5000`.

Opções do `run.py`: `--port 8080`, `--no-browser`, `--debug`.

## 2. Configurar a loja

Edite o `.env` (veja todas as opções em [`.env.example`](../.env.example)):

```ini
NOME_EMPRESA=Radar Auto Peças
BASE_LAT=-26.508484936938192
BASE_LON=-49.10542231274289
CIDADE_BUSCA=Jaraguá do Sul, SC
OWNTRACKS_TOKEN=uma-senha-forte
```

Edite `config/motoboys.json` com os nomes, as cores e o Tracker ID de cada motoboy.

## 3. Expor o servidor para os celulares

Os celulares dos motoboys usam dados móveis, então o servidor precisa de um endereço público. A opção mais simples é o **ngrok**:

1. Crie uma conta gratuita em [ngrok.com](https://ngrok.com), instale o `ngrok` (ou coloque o `ngrok.exe` na pasta `tools/`) e execute `ngrok config add-authtoken <token>`.
2. Reserve um domínio estático gratuito no painel do ngrok e coloque-o no `.env`: `NGROK_DOMAIN=seu-dominio.ngrok-free.app`.
3. Defina `OWNTRACKS_TOKEN` no `.env`. **Sem token o túnel não abre**, porque qualquer pessoa na internet poderia enviar posições falsas.
4. Pronto: o `GalviTracks.exe` abre o túnel automaticamente. Para abrir só o túnel, use `scripts\windows\tunel_ngrok.bat` (ou `ngrok http --domain=$NGROK_DOMAIN 5000`).

Alternativa: **Cloudflare Tunnel** (`cloudflared tunnel --url http://localhost:5000`).

**O que fica acessível pela internet.** Só o endpoint dos celulares (`/api/gps/owntracks`, que exige o token) e o `/api/health`. O painel e o restante da API respondem **403** a quem chega pelo túnel e continuam funcionando normalmente no computador da loja e na rede local. O servidor reconhece o acesso externo pelo cabeçalho `X-Forwarded-For` que o ngrok e o Cloudflare Tunnel acrescentam, pelo domínio `NGROK_DOMAIN` ou por um IP de origem público.

## 4. Configurar o OwnTracks no celular do motoboy

1. Instale o **OwnTracks** ([Android](https://play.google.com/store/apps/details?id=org.owntracks.android) / [iOS](https://apps.apple.com/app/owntracks/id692424691)).
2. Em **Preferências → Conexão**:
   - **Modo:** `HTTP`
   - **URL:** `https://<seu-dominio>/api/gps/owntracks`
   - **Identificação → Usuário:** qualquer valor (ex.: `motoboy`) · **Senha:** o valor de `OWNTRACKS_TOKEN` (se definido)
   - **Tracker ID:** o `tid` do motoboy em `config/motoboys.json` (ex.: `0`, `1`, `2`...)
3. Em **Preferências → Avançado**, escolha o modo de monitoramento **Move** (envio contínuo). Para atualizações mais frequentes, reduza o *locatorInterval* para 2–5 s.
4. Libere a localização **"o tempo todo"** e desative a otimização de bateria para o app.

Teste: com o app aberto, o ícone do motoboy deve se mover no painel em poucos segundos.

## 5. Demonstração sem celular

Monte uma rota para um motoboy no painel e execute:

```bash
python scripts/simular_motoboy.py --tid 0 --velocidade 40
```

Para demonstrar os alertas do painel:

```bash
python scripts/simular_motoboy.py --tid 0 --bateria 15      # bateria baixa (aparece na hora)
python scripts/simular_motoboy.py --tid 0 --parar-por 12    # para 12 min no meio da rota → "parado"
python scripts/simular_motoboy.py --tid 0 --cair-sinal      # para de enviar no meio da rota → "sem sinal" após 3 min
```

Os tempos dos alertas podem ser reduzidos no `.env` para apresentações (ex.: `ALERTA_SEM_SINAL_MIN=0.5`).

O script percorre o trajeto calculado enviando posições no mesmo formato do OwnTracks, o que serve para apresentações e testes.

## 6. Testes automatizados

```bash
pip install -r requirements-dev.txt
pytest
```

## Solução de problemas

| Sintoma | Causa provável / solução |
|---------|--------------------------|
| `python` não é reconhecido | Reinstale o Python marcando *Add to PATH*, ou use `py -3`. |
| Tempo aparece como "estimativa offline" | O OSRM público não respondeu em 3 s. Verifique a internet ou configure `OSRM_URL`. |
| Motoboy não se move | Confira URL, modo HTTP e Tracker ID no OwnTracks. O log do servidor mostra `tid desconhecido` ou `descartada pelo filtro`. |
| Erro 401 no OwnTracks | Senha diferente de `OWNTRACKS_TOKEN`. |
| Erro 403 no OwnTracks | `OWNTRACKS_TOKEN` vazio no servidor: pela internet o token é obrigatório. |
| "Disponível somente na rede da loja" | O painel foi aberto pelo endereço do túnel. Use `http://127.0.0.1:5000` no computador da loja ou o IP dele na rede local. |
| Porta 5000 ocupada | `python run.py --port 5050` (ajuste também o túnel). |
| Alerta "sem sinal" com o motoboy rodando normalmente | O OwnTracks está em modo econômico. Use o modo **Move** e desative a otimização de bateria do Android para o app. |
| Leituras descartadas com frequência | GPS com precisão ruim; aumente `GPS_PRECISAO_MAX_M` (ex.: 200). |
