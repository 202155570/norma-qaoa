#!/usr/bin/env bash
# README 6.8 on the AMD MI300X server (ROCm; torch still calls the device "cuda").
#  1) small map, N=20: d=3,4,5 x instances 0..9 x w=4,5 x p=1..5 (one process per d, sharing the GPU)
#  2) large N: train at w=5, check at w=6, p=1..5, (N, d) one after another
# The large stage starts only after the small one, so its GPU memory numbers are its own.
# Every step is resumable: rerun this script after an interruption.
#   usage: tmux new -d -s pps 'bash run_gpu_server.sh'
set -u
cd "$(dirname "$0")"
. .venv-rocm/bin/activate
export PADO_PRESET=gpu PF_DEVICE=cuda
export PPS_MEM_GB=${PPS_MEM_GB:-48} PPS_GPU_MEM_GB=${PPS_GPU_MEM_GB:-170} PPS_COMPILE_S=${PPS_COMPILE_S:-2400}
mkdir -p logs

for d in 3 4 5; do
  OMP_NUM_THREADS=4 python -u small.py run $d 0,1,2,3,4,5,6,7,8,9 5 4,5 small.jsonl >> logs/gpu_small_d${d}.log 2>&1 &
done
wait
echo "small done $(date -Is)" >> logs/gpu_small_d3.log

for n in 50 100 150; do for d in 3 4 5; do
  # exit 4: the w-check compile ran out of time; its training row is written, resume the chain
  while :; do
    OMP_NUM_THREADS=8 python -u large.py $n $d 5 5 large.jsonl >> large_gpu.log 2>&1
    [ $? -eq 4 ] || break
  done
done; done
echo "all done $(date -Is)" >> large_gpu.log
