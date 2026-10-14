#!/usr/bin/env bash
set -euo pipefail
CONFIG="${ODMRP_CONFIG:-/config/node.yaml}"
UNTIL="${ODMRP_UNTIL:-30}"
export PYTHONPATH="/app/backend${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m odmrp_sim.dataplane.neighbour_udp --config "$CONFIG" --until "$UNTIL"
