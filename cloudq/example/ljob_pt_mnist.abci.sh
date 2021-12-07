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
# $ cloudqcli submit --script ljob_pt_mnist.abci.sh --submit_to abci \
#                    --submit_opt '-g YOUR_GROUP'

source /etc/profile
source /etc/profile.d/modules.sh
module load singularitypro/3.7

export TMPDIR=$SGE_LOCALDIR

SIGURL=docker://nvcr.io/nvidia/pytorch:20.12-py3
SIGFILE=pytorch-20.12-py3.img

singularity pull $SIGFILE $SIGURL
wget -O cnn_mnist.py https://raw.githubusercontent.com/pytorch/examples/master/mnist/main.py
singularity exec --nv $SIGFILE python cnn_mnist.py

rm $SIGFILE
