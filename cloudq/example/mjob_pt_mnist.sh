#$ run_on:        ABCI
#$ project:       project001
#$ resource:      resource001
#$ n_resource:    1
#$ walltime:      1:00:00
#$ other_opts:    -p -400
#$ container_img: docker://nvcr.io/nvidia/pytorch:20.12-py3
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
# $ cloudqcli submit --script cloudq/example/mjob_pt_mnist.sh

wget -O cnn_mnist.py https://raw.githubusercontent.com/pytorch/examples/master/mnist/main.py
cq_container_run $CONTAINER_IMG0 python cnn_mnist.py
