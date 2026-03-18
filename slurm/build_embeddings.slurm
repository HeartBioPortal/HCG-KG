#!/bin/bash
#SBATCH --job-name=hcgkg-embeddings
#SBATCH --output=logs/slurm-embeddings-%j.out
#SBATCH --error=logs/slurm-embeddings-%j.err
#SBATCH --time=04:00:00
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G

set -euo pipefail

export HCG_KG_PROFILE="${HCG_KG_PROFILE:-hpc-large}"
cd "${PROJECT_ROOT:-$SLURM_SUBMIT_DIR}"
mkdir -p logs

hcg-kg build-embeddings --profile "$HCG_KG_PROFILE" --log-file "logs/build_embeddings_${SLURM_JOB_ID}.log"
