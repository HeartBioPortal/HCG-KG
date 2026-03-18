#!/usr/bin/env bash
set -euo pipefail

export HCG_KG_PROFILE="${HCG_KG_PROFILE:-local-dev}"

hcg-kg run-pipeline --profile "$HCG_KG_PROFILE" --input-glob "data/sample/*.json"
hcg-kg query --profile "$HCG_KG_PROFILE" --gene LDLR --pretty
