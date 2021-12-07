#!/bin/sh
#$ -l rt_G.small=1
#$ -cwd
#$-l h_rt=01:00:00
#
#======================================================================================
# Copyright 2021
#   National Institute of Advanced Industrial Science and Technology (AIST), Japan and
#   Hitachi, Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#======================================================================================
#
# Submission Example
# $ cloudqcli submit --script ljob_array.abci.sh --submit_to abci \
#                    --submit_opt '-g YOUR_GROUP -t 1-4'
#
# $ cloudqcli submit --script ljob_array.abci.sh --submit_to abci \
#                    --submit_opt '-g YOUR_GROUP' --array_tid 1-4

source /etc/profile
source /etc/profile.d/modules.sh
module load singularitypro/3.7

export TMPDIR=$SGE_LOCALDIR

SIGIMG=docker://nvcr.io/nvidia/pytorch:20.12-py3

IDX=$((SGE_TASK_ID-1))
TASKSETS=(
  "--epochs 4 --lr 1.0"
  "--epochs 4 --lr 0.9"
  "--epochs 8 --lr 1.0"
  "--epochs 8 --lr 0.9"
)

echo "Array Job Configuration"
echo "  SGE_TASK_ID:       ": $SGE_TASK_ID
echo "  SGE_TASK_FIRST:    ": $SGE_TASK_FIRST
echo "  SGE_TASK_LAST:     ": $SGE_TASK_LAST
echo "  SGE_TASK_STEPSIZE: ": $SGE_TASK_STEPSIZE
echo "  Train parameter:   ": ${TASKSETS[$IDX]}

wget -O cnn_mnist.py https://raw.githubusercontent.com/pytorch/examples/master/mnist/main.py
singularity exec --nv $SIGIMG python cnn_mnist.py ${TASKSETS[$IDX]}
