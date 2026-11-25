#!/usr/bin/env bash
# Prepara uma VM Ubuntu nova (Oracle Cloud) para o GalviTracks: Docker, firewall e swap.
# Uso, dentro da VM:  bash deploy/preparar_vm.sh
set -euo pipefail

echo "== Docker"
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sudo sh
fi
sudo usermod -aG docker "$USER"
sudo systemctl enable --now docker

echo "== Firewall da VM (as imagens Ubuntu da Oracle bloqueiam tudo além do SSH)"
# Também é preciso liberar 80 e 443 na Security List da VCN, no painel da Oracle (docs/nuvem.md).
for regra in "tcp 80" "tcp 443" "udp 443"; do
  set -- $regra
  if ! sudo iptables -C INPUT -p "$1" --dport "$2" -m state --state NEW -j ACCEPT 2>/dev/null; then
    sudo iptables -I INPUT 6 -p "$1" --dport "$2" -m state --state NEW -j ACCEPT
  fi
done
if command -v netfilter-persistent >/dev/null 2>&1; then
  sudo netfilter-persistent save
else
  sudo apt-get update && sudo DEBIAN_FRONTEND=noninteractive apt-get install -y iptables-persistent
  sudo netfilter-persistent save
fi

echo "== Swap de 2 GB (ajuda na VM pequena de 1 GB)"
if ! swapon --show | grep -q /swapfile; then
  sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo "/swapfile none swap sw 0 0" | sudo tee -a /etc/fstab >/dev/null
fi

echo "== Fuso horário"
sudo timedatectl set-timezone America/Sao_Paulo

echo
echo "Pronto. Saia e entre de novo no SSH (para o grupo docker valer) e siga o docs/nuvem.md."
