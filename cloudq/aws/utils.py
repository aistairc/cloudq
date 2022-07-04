# util: cloudq builder for AWS utilities
#
# Copyright 2022
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
import configparser
import dateutil.parser
from enum import Enum
import json
import logging
import re
import subprocess
import uuid
import yaml

logger = logging.getLogger('CloudQ Builder for AWS')


class STACK_TYPE(Enum):
    ''' List of stack type.
    '''
    UNKNOWN = 0
    VPC = 1
    NODES = 2


class STACK_STATUS(Enum):
    ''' List of status of stack.
    '''
    CREATE_IN_PROGRESS = 'CREATE_IN_PROGRESS'
    CREATE_COMPLETE = 'CREATE_COMPLETE'
    CREATE_FAILED = 'CREATE_FAILED'
    ROLLBACK_IN_PROGRESS = 'ROLLBACK_IN_PROGRESS'
    ROLLBACK_COMPLETE = 'ROLLBACK_COMPLETE'
    DELETE_FAILED = 'DELETE_FAILED'
    DELETE_IN_PROGRESS = 'DELETE_IN_PROGRESS'


class CLUSTER_STATUS(Enum):
    ''' List of status of AWS compute cluster.
    '''
    CREATING = 'CREATING'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'


ERROR_STACK_STATUS = [
    STACK_STATUS.CREATE_FAILED.value,
    STACK_STATUS.ROLLBACK_IN_PROGRESS.value,
    STACK_STATUS.ROLLBACK_COMPLETE.value
]


class Utils:
    ''' CloudQ builder for AWS utilities
    '''

    def __init__(self) -> None:
        '''Initialize.
        '''
        pass

    def get_data_dir_path(self) -> list:
        '''It returns path of data directory.

        Returns:
            list(dict): path of data directory.
        '''
        return os.path.join(os.path.dirname(__file__), 'data')

    def get_aws_info(self, profile: str = None) -> dict:
        '''It returns profile of AWS CLI.

        Args:
            profile (str):  the name of AWS profile.
        Returns:
            dict: profile of AWS CLI.
        '''
        aws_info = {}
        keys = ['aws_access_key_id', 'aws_secret_access_key', 'region']

        for key in keys:
            command = ["aws", "configure", "get"]
            if profile:
                command.append('--profile={}'.format(profile))
            command.append(key)
            result = self.exec_command(command)
            if len(result):
                aws_info[key] = result
        return aws_info

    def create_cloud_formation_stack(self, cluster_name: str, zone: str) -> dict:
        '''It creates Cloud Formation stack.

        Args:
            cluster_name (str): Name of AWS compute cluster.
            zone (str): Availability zone.
        Returns:
            dict: Informations of cloud formation stack.
        '''
        stack_info = {
            'StackName': '{}-vpc'.format(cluster_name),
            'BucketName': '{}-{}'.format(cluster_name, self.get_random_value()),
        }

        command = ['aws', 'cloudformation', 'create-stack']
        command += ['--stack-name', stack_info['StackName']]
        command += ['--template-body', 'file://{}'.format(
            os.path.join(self.get_data_dir_path(), 'cloud-stack.yaml'))]
        command += ['--parameters']
        command += ['ParameterKey=PublicCIDR,ParameterValue=10.0.0.0/24']
        command += ['ParameterKey=PrivateCIDR,ParameterValue=10.0.16.0/24']
        command += ['ParameterKey=AvailabilityZone,ParameterValue={}'.format(zone)]
        command += ['ParameterKey=InternetGatewayId,ParameterValue=']
        command += ['ParameterKey=BucketName,ParameterValue={}'.format(stack_info['BucketName'])]

        result = self.exec_command(command)
        if len(result):
            obj = json.loads(result)
            if 'StackId' in obj:
                stack_info['StackID'] = obj['StackId']
            else:
                raise Exception(result)
        return stack_info

    def get_availability_zone(self) -> str:
        '''It returns a availability_zone name

        Returns:
            str: Availability_zone name.
        '''
        zone = ''
        result = self.exec_command(['aws', 'ec2', 'describe-availability-zones'])
        if len(result):
            obj = json.loads(result)
            if 'AvailabilityZones' in obj:
                for zone_info in obj['AvailabilityZones']:
                    if zone_info['State'] == 'available':
                        zone = zone_info['ZoneName']
                        break
            else:
                raise Exception(result)
        return zone

    def is_stack_created(self, stack_info: dict, get_cf_info: bool = False) -> bool:
        '''It returns a stack creation status

        Args:
            stack_info (dict): Informations of cloud formation stack.
            get_cf_info (bool): If True, get information of cloud formation from 'Outputs'.
        Returns:
            bool: If the stack was created, return True, otherwise False.
        '''
        is_created = None
        result = self.exec_command(['aws', 'cloudformation', 'describe-stacks'])
        if len(result):
            obj = json.loads(result)
            if 'Stacks' in obj:
                for stack in obj['Stacks']:
                    if stack['StackId'] == stack_info['StackID']:
                        if stack['StackStatus'] == STACK_STATUS.CREATE_COMPLETE.value:
                            is_created = True
                            if get_cf_info:
                                for output in stack['Outputs']:
                                    if output['OutputKey'] == 'PublicSubnetId':
                                        stack_info['PublicSubnetID'] = output['OutputValue']
                                    elif output['OutputKey'] == 'PrivateSubnetId':
                                        stack_info['PrivateSubnetID'] = output['OutputValue']
                                    elif output['OutputKey'] == 'SecurityGroupId':
                                        stack_info['SecurityGroupID'] = output['OutputValue']
                        elif stack['StackStatus'] == STACK_STATUS.CREATE_IN_PROGRESS.value:
                            is_created = False
                        elif stack['StackStatus'] in ERROR_STACK_STATUS:
                            raise Exception('Stack creation failed. StackId:{}'.format(
                                stack_info['StackID']))
                        break
            else:
                raise Exception(result)
        if is_created is None:
            raise Exception('Stack is missing. StackId:{}'.format(stack_info['StackID']))
        return is_created

    def create_cluster_config(self, output_dir_path: str, default_aws_info: dict, cs_aws_info: dict,
                              stack_info: dict, keypair: str) -> str:
        '''It creates cluster config file

        Args:
            output_dir_path (str): Path of output directory.
            default_aws_info (dict):  default profile of AWS CLI.
            cs_aws_info (dict):  profile of AWS CLI to accessing cloud object storage.
            stack_info (dict): Informations of cloud formation stack.
            keypair (str): the name of EC2 key-pair.
        Returns:
            str: Path of Parallel Cluster configuretion file
        '''
        with open(os.path.join(self.get_data_dir_path(), 'cluster-config.yaml')) as fp:
            config = yaml.safe_load(fp)

        head_script = 's3://{}/on-head-node-start.sh'.format(stack_info['BucketName'])
        compute_script = 's3://{}/on-compute-node-start.sh'.format(stack_info['BucketName'])

        cloudq_version = self.get_cloudq_version()

        config['Region'] = default_aws_info['region']

        head_node = config['HeadNode']
        head_node['Networking']['SubnetId'] = stack_info['PublicSubnetID']
        head_node['Networking']['SecurityGroups'][0] = stack_info['SecurityGroupID']
        head_node['Ssh']['KeyName'] = keypair
        head_node['CustomActions']['OnNodeStart']['Script'] = head_script
        head_node['CustomActions']['OnNodeStart']['Args'] = [
            cs_aws_info['aws_access_key_id'],
            cs_aws_info['aws_secret_access_key'],
            cs_aws_info['region'],
            stack_info['BucketName'],
            cloudq_version
        ]
        head_node['Iam']['S3Access'][0]['BucketName'] = stack_info['BucketName']

        for compute_node in config['Scheduling']['SlurmQueues']:
            compute_node['Networking']['SubnetIds'][0] = stack_info['PrivateSubnetID']
            compute_node['Networking']['SecurityGroups'][0] = stack_info['SecurityGroupID']
            compute_node['CustomActions']['OnNodeStart']['Script'] = compute_script
            compute_node['CustomActions']['OnNodeStart']['Args'] = [
                cs_aws_info['aws_access_key_id'],
                cs_aws_info['aws_secret_access_key'],
                cs_aws_info['region'],
            ]
            compute_node['Iam']['S3Access'][0]['BucketName'] = stack_info['BucketName']

        output_file_path = os.path.join(output_dir_path, 'cluster-config.yaml')
        with open(output_file_path, mode='w') as fp:
            yaml.dump(config, fp)
        return output_file_path

    def create_cloudq_config(self, cluster_name: str, output_dir_path: str,
                             endpoint_url: str, bucket_name: str) -> str:
        '''It creates cloudq configuration file for headnode.

        Args:
            cluster_name (str): Name of AWS compute cluster.
            output_dir_path (str): Path of output directory.
            endpoint_url (str): The endpoint URL to accessing cloud object storage.
            bucket_name (str): The bucket name of cloud object storage.
        Returns:
            str: Path of CloudQ configuration file for headnode.
        '''
        src_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'config.ini')

        config = configparser.ConfigParser()
        config.read(src_path, encoding='UTF-8')
        config.set('default', 'name', cluster_name)
        config.set('agent', 'type', 'slurm')
        config.set('default', 'aws_profile', 'cs')
        config.set('default', 'cloudq_endpoint_url', endpoint_url)
        config.set('default', 'cloudq_bucket', bucket_name)
        config.set('agent', 'cloudq_directory', '/home/ec2-user/.cloudq')

        dst_path = os.path.join(output_dir_path, 'config.ini')
        with open(dst_path, 'w') as file:
            config.write(file)

        return dst_path

    def upload_setup_files(self, upload_files: list, bucket_name: str) -> None:
        '''It uploads setup files to S3_bucket.

        Args:
            upload_files (list(str)): List of upload file path.
            bucket_name (str): Name of S3 bucket.
        '''
        bucket_path = 's3://{}/'.format(bucket_name)
        for upload_file in upload_files:
            self.exec_command(['aws', 's3', 'cp', upload_file, bucket_path])

    def create_parallel_cluster_stack(self, cluster_name: str, cluster_config_path: str) -> dict:
        '''It creates Parallel Cluster stack.

        Args:
            cluster_name (str): Name of AWS compute cluster.
            cluster_config_path (str): Path of cluster configuretion file.
        Returns:
            dict: Informations of parallel cluster stack.
        '''
        stack_info = {
            'StackName': cluster_name,
        }
        command = [
            'pcluster',
            'create-cluster',
            '--cluster-name',
            stack_info['StackName'],
            '--cluster-configuration',
            cluster_config_path,
        ]
        # To ignore Warning, omit error checking.
        result = self.exec_command(command, False)
        if len(result):
            obj = json.loads(result)
            if 'cluster' in obj:
                stack_info['StackID'] = obj['cluster']['cloudformationStackArn']
            else:
                raise Exception(result)
        return stack_info

    def delete_parallel_cluster_stack(self, cluster_name: str) -> str:
        '''It deletes Parallel Cluster stack.

        Args:
            cluster_name (str): Name of AWS compute cluster.
        Return:
            stack_name (str): Name of Parallel Cluster stack.
        '''
        stack_name = cluster_name
        self.exec_command(['pcluster', 'delete-cluster', '--cluster-name', stack_name])
        return stack_name

    def delete_cloud_formation_stack(self, cluster_name: str) -> str:
        '''It deletes Cloud Formation stack.

        Args:
            cluster_name (str): Name of AWS compute cluster.
        Return:
            stack_name (str): Name of Cloud Formation stack.
        '''
        stack_name = '{}-vpc'.format(cluster_name)
        self.exec_command(['aws', 'cloudformation', 'delete-stack', '--stack-name', stack_name])
        return stack_name

    def get_bucket_name(self, cluster_name: str) -> str:
        '''It returns a name of S3 bucket.

        Args:
            cluster_name (str): Name of AWS compute cluster.
        Returns:
            dict: the S3 bucket name.
        '''
        bucket_name = ''
        stack_name = '{}-vpc'.format(cluster_name)
        result = self.exec_command(['aws', 'cloudformation', 'describe-stacks'])
        if len(result):
            obj = json.loads(result)
            if 'Stacks' in obj:
                for stack in obj['Stacks']:
                    if stack['StackName'] == stack_name:
                        for param in stack['Parameters']:
                            if param['ParameterKey'] == 'BucketName':
                                bucket_name = param['ParameterValue']
                                break
                        break
        return bucket_name

    def clear_bucket(self, bucket_name: str) -> None:
        '''It deletes Cloud Formation stack.

        Args:
            bucket_name (str): Name of S3 bucket.
        '''
        bucket_path = 's3://{}/'.format(bucket_name)
        self.exec_command(['aws', 's3', 'rm', bucket_path, '--recursive'])

    def is_stack_deleted(self, stack_name: str) -> bool:
        '''It returns a stack creation status

        Args:
            stack_name (str): Name of deleting stack.
        Returns:
            bool: If the stack was deleted, return True, otherwise False.
        '''
        is_deleted = True
        result = self.exec_command(['aws', 'cloudformation', 'describe-stacks'])
        if len(result):
            obj = json.loads(result)
            if 'Stacks' in obj:
                for stack in obj['Stacks']:
                    if stack['StackName'] == stack_name:
                        if stack['StackStatus'] in STACK_STATUS.DELETE_IN_PROGRESS.value:
                            is_deleted = False
                        elif stack['StackStatus'] in STACK_STATUS.DELETE_FAILED.value:
                            raise Exception('Stack deletion failed. stack_name:{}'.format(
                                stack_name))
                        break
            else:
                raise Exception(result)
        return is_deleted

    def get_cluster_list(self) -> list:
        '''It returns list of AWS compute clusters.

        Returns:
            list(dict): list of AWS compute clusters.
        '''
        clusters = []
        result = self.exec_command(['aws', 'cloudformation', 'describe-stacks'])
        if len(result):
            # parse stack list
            temp_cluster_list = {}
            obj = json.loads(result)
            if 'Stacks' in obj:
                for stack in obj['Stacks']:
                    cluster_name = None
                    stack_info = {}
                    result = re.match(r'^(\S+)\-vpc$', stack['StackName'])
                    if result:
                        cluster_name = result.group(1)
                        stack_info['Stack_type'] = STACK_TYPE.VPC
                    else:
                        for tag in stack['Tags']:
                            if tag['Key'] == 'parallelcluster:version':
                                cluster_name = stack['StackName']
                                stack_info['Stack_type'] = STACK_TYPE.NODES
                                break

                    if cluster_name:
                        stack_info['Status'] = stack['StackStatus']
                        stack_info['CreationTime'] = stack['CreationTime']
                        if cluster_name in temp_cluster_list:
                            temp_cluster_list[cluster_name].append(stack_info)
                        else:
                            temp_cluster_list[cluster_name] = [stack_info]
            else:
                raise Exception(result)

            # check clusters
            for cluster_name, cluster_info in temp_cluster_list.items():
                if len(cluster_info) == 2:
                    status = self.get_cluster_status(cluster_info[0], cluster_info[1])
                    creation_time = self.get_cluster_creation_time(cluster_info[0], cluster_info[1])
                    clusters.append({
                        'ClusterName': cluster_name,
                        'Status': status,
                        'CreationTime': creation_time
                    })
        return clusters

    def get_cluster_status(self, stack_1: dict, stack_2: dict) -> str:
        '''It returns a cluster status

        Args:
            stack_1 (dict): information of stack.
            stack_2 (dict): information of stack.
        Returns:
            str: cluster status.
        '''
        cluster_status = ''
        status_1 = stack_1['Status']
        status_2 = stack_2['Status']
        if ((status_1 == STACK_STATUS.CREATE_COMPLETE.value) and
                (status_2 == STACK_STATUS.CREATE_COMPLETE.value)):
            cluster_status = CLUSTER_STATUS.COMPLETED.value
        elif (status_1 in ERROR_STACK_STATUS or
                status_2 == ERROR_STACK_STATUS):
            cluster_status = CLUSTER_STATUS.FAILED.value
        elif (status_1 == STACK_STATUS.CREATE_IN_PROGRESS.value or
                status_2 == STACK_STATUS.CREATE_IN_PROGRESS.value):
            cluster_status = CLUSTER_STATUS.CREATING.value
        return cluster_status

    def get_cluster_creation_time(self, stack_1: dict, stack_2: dict) -> str:
        '''It returns a cluster creation time

        Args:
            stack_1 (dict): information of stack.
            stack_2 (dict): information of stack.
        Returns:
            str: cluster creation time.
        '''
        creation_time = ''
        if (stack_1['Status'] == STACK_STATUS.CREATE_COMPLETE.value and
                stack_2['Status'] == STACK_STATUS.CREATE_COMPLETE.value):
            time_1 = dateutil.parser.parse(stack_1['CreationTime'])
            time_2 = dateutil.parser.parse(stack_2['CreationTime'])
            if time_1 > time_2:
                creation_time = time_1
            else:
                creation_time = time_2
        return creation_time

    def get_random_value(self) -> str:
        '''It returns a randomized characters

        Returns:
            str: a randomized characters(8 characters hex value).
        '''
        return str(uuid.uuid4())[:8]

    def get_cloudq_version(self) -> str:
        '''It returns CloudQ's version string.

        Returns:
            str: CloudQ's version string
        '''
        version = ''
        output = self.exec_command(["pip", "show", "cloudq"])
        if len(output):
            for info in output.splitlines():
                reg_result = re.match(r'^\s*Version:\s*(\S+)\s*$', info)
                if reg_result:
                    version = reg_result.group(1)
                    break
        return version

    def exec_command(self, command: list, error_check: bool = True) -> str:
        '''It executes a command in a subprocess

        Args:
            command (list(str)): command and parameters.
        Returns:
            str: output of command.
        '''
        proc = subprocess.run(
            ' '.join(command), shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if error_check and proc.stderr:
            raise Exception('Command failed. : {}'.format(proc.stderr.decode()))
        if not proc.stdout:
            return ''
        return proc.stdout.decode().rstrip()
