#!/usr/bin/env bash
# One-time Termux setup for Pyhost
set -e
cd "$(dirname "$0")"
termux-setup-storage || true
pkg update -y
pkg install -y python unzip
pip install -r requirements.txt
echo
echo "Setup done. Ekhon chalao:  bash start.sh"
