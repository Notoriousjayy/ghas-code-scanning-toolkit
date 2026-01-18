#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

export GH_TOKEN="${GH_TOKEN:-}"
python scripts/apply_policy.py --config .ghas-toolkit.json
python scripts/triage_and_act.py --rules triage-rules.json
