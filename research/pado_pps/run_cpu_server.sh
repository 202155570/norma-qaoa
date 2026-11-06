#!/usr/bin/env bash
# README 6.8 on a CPU-only Linux server (no GPU): the small map runs one process per
# (d, instance) in parallel, the large map runs its (N, d) configurations one after another.
# Every step is resumable: rerun this script after an interruption.
#   usage: tmux new -d -s pps 'bash run_cpu_server.sh'
set -u
cd "$(dirname "$0")"
. .venv/bin/activate
export PADO_PRESET=cpu PF_DEVICE=cpu
export PPS_MEM_GB=${PPS_MEM_GB:-48} PPS_COMPILE_S=${PPS_COMPILE_S:-2400}
mkdir -p logs

# 1) small map, N=20: d=3,4,5 x instances 0..2 x w=4,5 x p=1..5
for d in 3 4 5; do for s in 0 1 2; do
  OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 \
    python -u small.py run $d $s 5 4,5 small.jsonl >> logs/small_d${d}_i${s}.log 2>&1 &
done; done

# 2) large N: train at w=4, check at w=5, p=1..5
(
  for n in 50 100 150; do for d in 3 4 5; do
    OMP_NUM_THREADS=3 MKL_NUM_THREADS=3 python -u large.py $n $d 5 4 large.jsonl >> large.log 2>&1
  done; done
) &
wait
echo "all done $(date -Is)"
