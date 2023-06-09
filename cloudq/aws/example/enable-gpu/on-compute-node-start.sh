#!/bin/bash
#
#======================================================================================
# Copyright 2022-2023
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
echo "on-compute-node-start script was started. args: $#"

amazon-linux-extras install -y python3.8

curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
./aws/install

# Docker and Singularity installations.
amazon-linux-extras install docker -y

service docker start

usermod -a -G docker ec2-user

yum groupinstall -y 'Development Tools'
yum install -y libseccomp-devel glib2-devel squashfs-tools cryptsetup runc

export VERSION=1.19.5 OS=linux ARCH=amd64
wget https://dl.google.com/go/go$VERSION.$OS-$ARCH.tar.gz
tar -C /usr/local -xzvf go$VERSION.$OS-$ARCH.tar.gz
rm go$VERSION.$OS-$ARCH.tar.gz

export GOPATH=/home/go
export GOCACHE=/home/go/cache
export PATH=/usr/local/go/bin:${PATH}:${GOPATH}/bin

go get -u github.com/golang/dep/cmd/dep

git clone --recurse-submodules https://github.com/sylabs/singularity.git
cd singularity
git checkout --recurse-submodules v3.11.0
./mconfig
make -C builddir
make -C builddir install

# Setup for using CUDA-enabled GPUs.
amazon-linux-extras install epel
yum install kernel-devel-$(uname -r) kernel-headers-$(uname -r)

ARCH=$( /bin/arch )
distribution=rhel7
sudo yum-config-manager --add-repo http://developer.download.nvidia.com/compute/cuda/repos/$distribution/${ARCH}/cuda-$distribution.repo
yum install -y nvidia-driver-latest-dkms cuda cuda-drivers

export CUDA_HOME=/usr/local/cuda-11.0
export PATH=/usr/local/go/bin:${PATH}:${GOPATH}/bin

distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-container-runtime/$distribution/nvidia-container-runtime.repo tee /etc/yum.repos.d/nvidia-container-runtime.repo
sudo yum install -y nvidia-container-runtime


echo "on-compute-node-start script was completed."
