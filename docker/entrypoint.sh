#!/bin/sh
# Roda a cada partida do contêiner, antes do comando principal.
set -e

python /app/scripts/bootstrap.py

# exec substitui este shell pelo processo da aplicação, que vira o PID 1 e
# recebe diretamente os sinais de parada do Docker.
exec "$@"
