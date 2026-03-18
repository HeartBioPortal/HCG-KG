#!/bin/bash
#SBATCH --job-name=hcgkg-normalize
#SBATCH --output=logs/slurm-normalize-%j.out
#SBATCH --error=logs/slurm-normalize-%j.err
#SBATCH --time=04:00:00
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G

set -euo pipefail

export HCG_KG_PROFILE="${HCG_KG_PROFILE:-hpc-large}"
export HCG_KG_INPUT_GLOB="${HCG_KG_INPUT_GLOB:?Set a parsed JSON glob before submission}"

cd "${PROJECT_ROOT:-$SLURM_SUBMIT_DIR}"
mkdir -p logs

hcg-kg normalize --profile "$HCG_KG_PROFILE" --input-glob "$HCG_KG_INPUT_GLOB" --log-file "logs/normalize_${SLURM_JOB_ID}.log"
