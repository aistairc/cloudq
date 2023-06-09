# add_logs: Add head node logs to Amazon CloudWatch Logs
#
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
import os
import json

cloudwatch_file = (
    '/opt/aws/amazon-cloudwatch-agent/etc/' +
    'amazon-cloudwatch-agent.d/file_amazon-cloudwatch-agent.json')

if not os.path.exists(cloudwatch_file):
    print('file is not exist. file: {}'.format(cloudwatch_file))
else:
    try:
        with open(cloudwatch_file, 'r') as fileread:
            json_load = json.load(fileread)
            collect_list = json_load['logs']['logs_collected']['files']['collect_list']

            for collect in collect_list:
                org_log_stream_name = collect['log_stream_name']
                log_group_name = collect['log_group_name']
                break

            if '.' not in org_log_stream_name:
                print('log_stream_name is different from expected.(dot not in)')
            else:
                # add CloudQ Agent log
                log_stream_name = org_log_stream_name.split('.')
                log_stream_name[2] = 'cloudqd-log'
                log_stream_name = '.'.join(log_stream_name)
                file_path = '/home/ec2-user/.cloudq/cloudqd.log'
                timestamp_format = '%Y-%m-%d %H:%M:%S,%f'

                collect_list.append({
                    'log_stream_name': log_stream_name,
                    'file_path': file_path,
                    'timestamp_format': timestamp_format,
                    'log_group_name': log_group_name
                })

                # add SSH access log
                log_stream_name = org_log_stream_name.split('.')
                log_stream_name[2] = 'sshd'
                log_stream_name = '.'.join(log_stream_name)
                file_path = '/var/log/secure_sshd'
                timestamp_format = '%Y-%m-%d %H:%M:%S,%f'

                collect_list.append({
                    'log_stream_name': log_stream_name,
                    'file_path': file_path,
                    'timestamp_format': timestamp_format,
                    'log_group_name': log_group_name
                })

                json_load['logs']['logs_collected']['files']['collect_list'] = collect_list

                # over write file_amazon-cloudwatch-agent.json
                with open(cloudwatch_file, 'w') as filewrite:
                    json.dump(json_load, filewrite, indent=2)
        print('add log end.')
    except Exception as e:
        print(e)
