# GalviTracks na nuvem (Oracle Cloud)

Com o servidor na nuvem, o GalviTracks funciona 24 horas sem depender do computador da loja:

- os **celulares** mandam a posição direto para `https://SEU-DOMINIO/api/gps/owntracks` (sem ngrok);
- o **painel** abre em `https://SEU-DOMINIO` de qualquer computador ou celular, sempre com login;
- o **banco** fica no servidor, com **backup diário** às 3h (últimos 14 dias).

```
Celulares (OwnTracks) ──HTTPS──┐
                               ├──> Caddy (HTTPS automático) ──> GalviTracks (Docker) ──> data/radar.db
Navegador (painel)  ──HTTPS──┘                                    backup diário ──> data/backup/
```

| Arquivo | Para que serve |
|---|---|
| [`Dockerfile`](../Dockerfile) | Imagem do servidor (x86 e ARM) |
| [`compose.yml`](../compose.yml) | Sobe o app, o Caddy (HTTPS) e o backup |
| [`deploy/Caddyfile`](../deploy/Caddyfile) | Proxy reverso com certificado Let's Encrypt |
| [`deploy/env.nuvem.example`](../deploy/env.nuvem.example) | Modelo do `.env.nuvem` (domínio e senhas) |
| [`deploy/preparar_vm.sh`](../deploy/preparar_vm.sh) | Instala Docker, abre o firewall e cria swap na VM |
| [`scripts/backup_banco.py`](../scripts/backup_banco.py) | Backup diário do banco |

## 1. Comprar o domínio

No [registro.br](https://registro.br) (precisa de CPF ou CNPJ), compre o domínio, por exemplo `galvitracks.com.br`. Deixe o DNS no próprio registro.br (*DNS do Registro.br*): o registro que aponta para o servidor é criado no passo 4.

## 2. Criar a conta e a VM na Oracle

1. Crie a conta em [oracle.com/cloud/free](https://www.oracle.com/cloud/free/). Escolha a **região São Paulo** (*Brazil East*): ela não pode ser trocada depois. O cartão é pedido só para verificação; os recursos *Always Free* não são cobrados.
2. Menu **Compute → Instances → Create instance**:
   - **Image:** Canonical Ubuntu 24.04 ou Oracle Linux 9 (o `preparar_vm.sh` funciona nos dois; no Oracle Linux o usuário do SSH é `opc` em vez de `ubuntu`). Escolha o shape antes da imagem: a lista só mostra imagens compatíveis.
   - **Shape:** *Ampere* `VM.Standard.A1.Flex` com 2 OCPUs e 12 GB (grátis). Se aparecer *out of capacity*, tente outro *Availability Domain* ou use a `VM.Standard.E2.1.Micro` (AMD, 1 GB, também grátis: dá conta do GalviTracks com o swap do passo 5).
   - **Networking:** deixe criar a VCN nova, com IP público.
   - **SSH keys:** *Paste public keys* e cole a chave pública (a do seu PC ou a que o Claude gerou para fazer a implantação).
3. Anote o **IP público** da VM.

## 3. Liberar as portas 80 e 443 na Oracle

Na página da VM: **Subnet → Security List (Default) → Add Ingress Rules**, duas regras com *Source CIDR* `0.0.0.0/0`, protocolo TCP, portas de destino `80` e `443`. (O firewall de dentro da VM é aberto pelo script do passo 5.)

## 4. Apontar o domínio para a VM

No registro.br, em **DNS → Editar zona**, crie um registro **A** com o nome vazio (o próprio domínio) e o valor = IP público da VM. Se quiser também `www`, crie outro **A** para `www`. A propagação leva de minutos a algumas horas; confira com `nslookup galvitracks.com.br`.

## 5. Instalar o GalviTracks na VM

Do seu computador:

```bash
ssh ubuntu@IP_DA_VM
```

Na VM:

```bash
git clone https://github.com/AndreeSpecht/GalviTracks.git
cd GalviTracks
bash deploy/preparar_vm.sh          # Docker, firewall, swap e fuso
exit                                 # saia e entre de novo para o grupo docker valer
```

Entre de novo (`ssh ubuntu@IP_DA_VM`), depois:

```bash
cd GalviTracks
cp deploy/env.nuvem.example .env.nuvem
nano .env.nuvem                      # DOMINIO, OWNTRACKS_TOKEN e SECRET_KEY
```

Leve o banco da loja (clientes, histórico e usuários). No PC da loja, **com o GalviTracks fechado**:

```bash
scp data/radar.db ubuntu@IP_DA_VM:~/GalviTracks/data/radar.db
```

E suba tudo:

```bash
docker compose up -d --build
docker compose ps                    # app "healthy", caddy e backup "Up"
```

Na primeira subida o Caddy pede o certificado HTTPS; em um minuto `https://SEU-DOMINIO` abre a tela de login. Entre com os mesmos usuários de antes. Para criar ou redefinir usuários pelo servidor:

```bash
docker compose exec app python scripts/criar_usuario.py maria --nome "Maria" --perfil operador
docker compose exec app python scripts/criar_usuario.py --listar
```

## 6. Trocar o endereço nos celulares

No OwnTracks de cada motoboy (*Configurações → Conexão*):

- **Modo:** HTTP
- **Host / URL:** `https://SEU-DOMINIO/api/gps/owntracks`
- **Identificação:** usuário qualquer (ex.: o nome do motoboy) e **senha** = `OWNTRACKS_TOKEN` do `.env.nuvem`
- **Tracker ID:** o do motoboy em `config/motoboys.json` (0, 1, 2, 3)

Dê uma volta no quarteirão e confira o motoboy no mapa.

## 7. No dia a dia

- **Loja:** abra `https://SEU-DOMINIO` no navegador (pode fixar na barra de tarefas). O `GalviTracks.exe` e o ngrok deixam de ser necessários.
- **Atualizar o sistema** (depois de um `git push`):

  ```bash
  cd GalviTracks && git pull && docker compose up -d --build
  ```

  A rota em andamento e o banco ficam em `data/` e sobrevivem à atualização.
- **Ver os logs:** `docker compose logs -f app`
- **Backups:** `data/backup/radar_AAAA-MM-DD.db` na VM. Para guardar uma cópia fora da nuvem: `scp ubuntu@IP_DA_VM:~/GalviTracks/data/backup/radar_*.db .`
- **Restaurar um backup:** `docker compose stop app`, copie o arquivo do backup por cima de `data/radar.db` (e apague `data/radar.db-wal` e `data/radar.db-shm`), `docker compose start app`.

## Segurança

- O painel exige login (`ACESSO_PAINEL_INTERNET=1` e cookie só por HTTPS, já definidos no `compose.yml`); a criação do primeiro gestor pela internet continua bloqueada (use `criar_usuario.py`).
- O GPS só é aceito com o `OWNTRACKS_TOKEN`.
- O limite de tentativas de login usa o IP real de quem acessa: o Caddy informa o IP pelo `X-Forwarded-For`, e o app só confia nesse cabeçalho vindo da rede interna do Docker (`PROXIES_CONFIAVEIS`).
- O `.env.nuvem` tem as senhas e não vai para o Git.
- Com a nuvem como banco oficial, o `data/radar.db` deixa de ser versionado no GitHub (o repositório é público). Versões antigas continuam no histórico do Git.
