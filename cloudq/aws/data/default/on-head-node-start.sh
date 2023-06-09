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
echo "on-head-node-start script was started. args: $#"

amazon-linux-extras install -y python3.8

curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
./aws/install

aws configure set aws_access_key_id $1 --profile cs
aws configure set aws_secret_access_key $2 --profile cs
aws configure set region $3 --profile cs

sudo -u ec2-user aws configure set aws_access_key_id $1 --profile cs
sudo -u ec2-user aws configure set aws_secret_access_key $2 --profile cs
sudo -u ec2-user aws configure set region $3 --profile cs

pip3.8 install 'cloudq'
aws s3 cp s3://$4/config.ini $(pip3.8 show cloudq | grep Location | cut -d ' ' -f 2)/cloudq/data/config.ini
pip3.8 install certifi

aws s3 cp s3://$4/cloudq.service ./
cp ./cloudq.service /etc/systemd/system
chown root:root /etc/systemd/system/cloudq.service
chmod 644 /etc/systemd/system/cloudq.service

mkdir -p /opt/cloudq/bin
chmod 755 /opt/cloudq/bin
aws s3 cp s3://$4/autoexec.sh ./
cp ./autoexec.sh /opt/cloudq/bin
chown root:root /opt/cloudq/bin/autoexec.sh
chmod 755 /opt/cloudq/bin/autoexec.sh

systemctl daemon-reload
systemctl enable cloudq.service
systemctl start cloudq.service

echo :programname, isequal, \"sshd\" /var/log/secure_sshd > /etc/rsyslog.d/31-secure-sshd.conf
systemctl restart rsyslog

aws s3 cp s3://$4/add_log.py ./
python3 add_log.py
systemctl restart amazon-cloudwatch-agent

echo "on-head-node-start script was completed."
