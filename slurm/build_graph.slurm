#!/bin/bash
#SBATCH --job-name=hcgkg-build-graph
#SBATCH --partition=gpu
#SBATCH --output=logs/slurm-build-graph-%j.out
#SBATCH --error=logs/slurm-build-graph-%j.err
#SBATCH --time=08:00:00
#SBATCH --cpus-per-task=32
#SBATCH --mem=128G
#SBATCH --gres=gpu:1

set -euo pipefail

export HCG_KG_PROFILE="${HCG_KG_PROFILE:-hpc-large}"
cd "${PROJECT_ROOT:-$SLURM_SUBMIT_DIR}"
mkdir -p logs

hcg-kg build-graph --profile "$HCG_KG_PROFILE" --log-file "logs/build_graph_${SLURM_JOB_ID}.log"
