#!/bin/bash
#SBATCH --job-name=hcgkg-llm-pipeline
#SBATCH --output=logs/slurm-llm-pipeline-%j.out
#SBATCH --error=logs/slurm-llm-pipeline-%j.err
#SBATCH --time=08:00:00
#SBATCH --cpus-per-task=8
#SBATCH --mem=128G
#SBATCH --gres=gpu:1

set -euo pipefail

export HCG_KG_PROFILE="${HCG_KG_PROFILE:-hpc-llm}"
export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"
export TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-$HF_HOME}"

cd "${PROJECT_ROOT:-$SLURM_SUBMIT_DIR}"
mkdir -p logs

hcg-kg run-pipeline --profile "$HCG_KG_PROFILE" --force --log-file "logs/llm_pipeline_${SLURM_JOB_ID}.log"
