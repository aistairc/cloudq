# cloudqaws: cloudq builder for AWS
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
import sys
import argparse
from functools import cmp_to_key
import configparser
from enum import Enum
import logging
import tempfile
import time
import traceback
import shutil

from .utils import Utils

PROCESS_NAME = 'CloudQ Builder for AWS'
'''Name of this process.
'''
LOG_FILE = 'cloudqaws.log'
'''File path of log file.
'''
LOG_FILE_FORMAT = '%(asctime)s : %(levelname)-8s : %(message)s'
'''Format of log file.
'''
LOG_STDOUT_FORMAT = '%(message)s'
'''Format of stdout.
'''
CONFIG_FILE = 'config.ini'
'''File path of configuration file.
'''
CONFIG_FILE_ENCODING = 'utf-8'
'''Encoding of configuration file.
'''

CONFIG_PARAMS = [
    {'section': 'default',  'key': 'stack_check_interval',
     'type': int,   'mandatory': True,    'min': 1},
    {'section': 'default',  'key': 'log_level',
     'type': str, 'mandatory': False,  'default': 'INFO'},
]
'''Definition of mandatory configuration parameters.
'''


class MESSAGES(Enum):
    ''' List of console messages.
    '''

    # success
    CREATE_COMPLETED = 'AWS compute cluster ({}) has been created.'
    DELETE_COMPLETED = 'AWS compute cluster ({}) has been deleted.'
    PRESET_COMPLETED = 'Preset ({}) has been created.'
    INFORMATION_PRESET_AFTER = 'Please change the contents of the preset according to your computing environment.'

    # success
    STACK_CREATING = 'The stack ({}) is creating. Please wait a minute.'
    STACK_DELETING = 'The stack ({}) is deleting. Please wait a minute.'

    # error
    CONFIG_PARAM_NOT_SPECIFIED = 'Mandatory configuration parameter is not specified: [{}] {}'
    INVALID_CONFIG_PARAM = 'Invalid configuration parameter: [{}] {} = {}'
    CLUSTER_NAME_NOT_SPECIFIED = 'Cluster name is not specified.'
    KEY_PAIR_NOT_SPECIFIED = 'EC2 Key-pair file is not specified.'
    KEY_PAIR_NOT_FOUND = 'The EC2 Key-pair file is not found: {}'
    PROFILE_NOT_SPECIFIED = 'AWS profile is not specified.'
    ENDPOINT_NOT_SPECIFIED = 'Endpoint URL is not specified.'
    BUCKET_NOT_SPECIFIED = 'Bucket name is not specified.'
    NO_CONFIG_FILE = 'The configuration file is not found: {}'
    INVALID_PRESET_NAME = 'Invalid specified preset name.'
    ERROR_MESSAGE_PRESET = 'Failed to create Preset.'
    ERROR_MESSAGE_CREATE = 'Failed to create AWS compute cluster.'
    ERROR_MESSAGE_DELETE = 'Failed to delete AWS compute cluster.'


def create_cluster(config: configparser.ConfigParser, args: argparse.Namespace):
    '''It creates a AWS compute cluster.

    Args:
        config (configparser.ConfigParser): CloudQ Builder for AWS configuration.
        args (argparse.Namespace): Arguments for cluster creation.
            Used arguments are ``name``, ``keypair``, ``cs_profile``,
            ``cs_endpoint``, ``cs_bucket``, ``zone``.
    '''
    logger.debug('create_cluster start.')

    if not args.name:
        raise Exception(MESSAGES.CLUSTER_NAME_NOT_SPECIFIED.value)
    elif not args.keypair:
        raise Exception(MESSAGES.KEY_PAIR_NOT_SPECIFIED.value)
    elif not args.cs_profile:
        raise Exception(MESSAGES.PROFILE_NOT_SPECIFIED.value)
    elif not args.cs_endpoint:
        raise Exception(MESSAGES.ENDPOINT_NOT_SPECIFIED.value)
    elif not args.cs_bucket:
        raise Exception(MESSAGES.BUCKET_NOT_SPECIFIED.value)

    default_aws_info = Utils().get_aws_info()
    cs_aws_info = Utils().get_aws_info(args.cs_profile)

    if args.zone:
        zone = args.zone
    else:
        zone = Utils().get_availability_zone()

    if args.preset_name:
        preset_data = args.preset_name
    else:
        preset_data = 'default'

    cf_stack_info = Utils().create_cloud_formation_stack(args.name, zone, preset_data)
    while not Utils().is_stack_created(cf_stack_info, True):
        logger.info(MESSAGES.STACK_CREATING.value.format(cf_stack_info['StackName']))
        time.sleep(config.getint('default', 'stack_check_interval'))

    with tempfile.TemporaryDirectory() as temp_dir_path:
        cluster_config_path = Utils().create_cluster_config(
            temp_dir_path, default_aws_info, cs_aws_info, cf_stack_info, args.keypair, preset_data)
        cloudq_config_path = Utils().create_cloudq_config(
            args.name, temp_dir_path, args.cs_endpoint, args.cs_bucket)
        cloudq_autoexec_path = Utils().create_autoexec_config(temp_dir_path, log_level, preset_data)

        Utils().upload_setup_files([
            cloudq_config_path,
            os.path.join(os.path.expanduser(
                '~/.cloudq/aws/'), preset_data, 'on-head-node-start.sh'),
            os.path.join(os.path.expanduser(
                '~/.cloudq/aws/'), preset_data, 'on-compute-node-start.sh'),
            os.path.join(os.path.expanduser(
                '~/.cloudq/aws/'), preset_data, 'add_log.py'),
            cloudq_autoexec_path,
            os.path.join(os.path.expanduser(
                '~/.cloudq/aws/'), preset_data, 'cloudq.service'),
        ], cf_stack_info['BucketName'])
        pc_stack_info = Utils().create_parallel_cluster_stack(args.name, cluster_config_path)
        while not Utils().is_stack_created(pc_stack_info):
            logger.info(MESSAGES.STACK_CREATING.value.format(pc_stack_info['StackName']))
            time.sleep(config.getint('default', 'stack_check_interval'))

    logger.info(MESSAGES.CREATE_COMPLETED.value.format(args.name))
    logger.debug('create_cluster ended.')


def delete_cluster(config: configparser.ConfigParser, args: argparse.Namespace):
    '''It deletes a AWS compute cluster.

    Args:
        config (configparser.ConfigParser): CloudQ Builder for AWS configuration.
        args (argparse.Namespace): Arguments for cluster deletion.
            Used arguments are ``name``.
    '''
    logger.debug('delete_cluster start.')

    if not args.name:
        raise Exception(MESSAGES.CLUSTER_NAME_NOT_SPECIFIED.value)

    bucket_name = Utils().get_bucket_name(args.name)

    pc_stack_name = Utils().delete_parallel_cluster_stack(args.name)
    while not Utils().is_stack_deleted(pc_stack_name):
        logger.info(MESSAGES.STACK_DELETING.value.format(pc_stack_name))
        time.sleep(config.getint('default', 'stack_check_interval'))

    Utils().clear_bucket(bucket_name)

    cf_stack_name = Utils().delete_cloud_formation_stack(args.name)
    while not Utils().is_stack_deleted(cf_stack_name):
        logger.info(MESSAGES.STACK_DELETING.value.format(cf_stack_name))
        time.sleep(config.getint('default', 'stack_check_interval'))

    logger.info(MESSAGES.DELETE_COMPLETED.value.format(args.name))
    logger.debug('delete_cluster ended.')


def list_clusters(config: configparser.ConfigParser, args: argparse.Namespace):
    '''It shows list of AWS compute clusters.

    Args:
        config (configparser.ConfigParser): CloudQ CLI configuration.
        args (argparse.Namespace): Arguments for listing a clusters.
    '''
    logger.debug('list_clusters start.')

    cluster_list = Utils().get_cluster_list()

    name_len = len('Cluster Name')
    for cluster in cluster_list:
        name_len = max(name_len, len(cluster['ClusterName']))

    # sort by creation time.
    def cluster_sort(a: dict, b: dict) -> int:
        if a['CreationTime'] == b['CreationTime']:
            return 0
        elif a['CreationTime'] == '':
            return 1
        elif b['CreationTime'] == '':
            return -1
        else:
            if a['CreationTime'] < b['CreationTime']:
                return -1
            else:
                return 1
    cluster_list = sorted(cluster_list, key=cmp_to_key(cluster_sort))

    # output cluster list
    logger.info('  '.join(['Cluster Name'.ljust(name_len, ' '),
                           'Status'.ljust(9, ' '),
                           'Creation Time']))
    logger.info('-' * (name_len + 36))
    for cluster in cluster_list:
        creation_time = ''
        if not cluster['CreationTime'] == '':
            creation_time = cluster['CreationTime'].strftime('%Y/%m/%d %H:%M:%S %Z')
        logger.info('  '.join([cluster['ClusterName'].ljust(name_len, ' '),
                               cluster['Status'].ljust(9, ' '),
                               creation_time]))

    logger.debug('list_clusters ended.')


def preset_cluster(config: configparser.ConfigParser, args: argparse.Namespace):
    '''It creates a preset.

    Args:
        config (configparser.ConfigParser): Preset configuration.
        args (argparse.Namespace): Arguments for directory name.
            Used arguments are ``preset_name``.
    '''
    logger.debug('preset_cluster start.')
    try:
        if args.preset_name:
            preset_dir_name = args.preset_name
            path = os.path.join(os.path.expanduser('~/.cloudq/aws/'), args.preset_name)
            if not os.path.isdir(path):
                dir_default = os.path.join(os.path.dirname(__file__), 'data', 'default')
                shutil.copytree(dir_default, path)
        else:
            preset_dir_name = 'default'
    except Exception:
        raise Exception(MESSAGES.INVALID_PRESET_NAME.value)

    logger.info(MESSAGES.PRESET_COMPLETED.value.format(preset_dir_name))
    logger.info(MESSAGES.INFORMATION_PRESET_AFTER.value)
    logger.debug('preset_cluster ended.')


def _check_config(config: configparser.ConfigParser) -> None:
    '''It checks configuration parameters.

    Args:
        config (configparser.ConfigParser): CloudQ CLI configuration.
    '''
    for param in CONFIG_PARAMS:
        # check existance of section
        if not param['section'] in config.sections():
            # create empty section
            config[param['section']] = {}

        try:
            if param['type'] is str:
                # string parameter
                value = config.get(param['section'], param['key'])
                if param['mandatory'] and 0 >= len(value):
                    raise Exception(MESSAGES.INVALID_CONFIG_PARAM.value.format(
                        param['section'], param['key'], '(empty)'))

            elif param['type'] is int:
                # integer parameter
                value = config.getint(param['section'], param['key'])
                if param['min'] > value:
                    raise Exception(MESSAGES.INVALID_CONFIG_PARAM.value.format(
                        param['section'], param['key'], value))

        except configparser.NoOptionError:
            if param['mandatory']:
                # if this parameter is mandatory, raise exception.
                raise Exception(MESSAGES.CONFIG_PARAM_NOT_SPECIFIED.value.format(
                    param['section'], param['key']))
            else:
                # if this parameter is optional, set detault value.
                config[param['section']][param['key']] = param['default']


def show_config(config: configparser.ConfigParser) -> None:
    '''It checks configuration parameters.

    Args:
        config (configparser.ConfigParser): CloudQ CLI configuration.
    '''
    for param in CONFIG_PARAMS:
        try:
            logger.info('section={}, key={}, value={}'.format(
                param['section'], param['key'],
                config.get(param['section'], param['key'])
            ))
        except configparser.NoOptionError:
            logger.info('section={}, key={}, value=None'.format(
                param['section'], param['key']
            ))


def _construct_argparser() -> argparse.ArgumentParser:
    '''It returns arguemnt parser.

    Returns:
        (argparse.ArgumentParser): the argument parser of CloudQ client.
    '''
    parser = argparse.ArgumentParser(description='CloudQ Builder for AWS', add_help=True)
    subparsers = parser.add_subparsers(dest='subcommand')
    subparsers.required = True

    # create
    help_message_create = 'Create a AWS compute cluster'
    parser_create = subparsers.add_parser('create', help=help_message_create,
                                          description=help_message_create)
    parser_create.add_argument('--name', help='specify cluster name.')
    parser_create.add_argument('--keypair', help='specify EC2 key-pair name.')
    parser_create.add_argument('--zone', help='specify available zone.')
    parser_create.add_argument(
        '--cs_profile',
        help='specify AWS profile to access an object storage that stores CloudQ jobs.')
    parser_create.add_argument(
        '--cs_endpoint',
        help='specify the endpoint URL of an object storage that stores CloudQ jobs.')
    parser_create.add_argument(
        '--cs_bucket',
        help='specify the name of the bucket where CloudQ jobs are stored.')
    parser_create.add_argument('--preset_name', help='specify preset name. ')
    parser_create.add_argument('--log_level', help='specify log level. ')
    parser_create.set_defaults(func=create_cluster)

    # delete
    help_message_delete = 'Delete a AWS compute cluster'
    parser_delete = subparsers.add_parser('delete', help=help_message_delete,
                                          description=help_message_delete)
    parser_delete.add_argument('--name', help='specify cluster name.')
    parser_delete.add_argument('--log_level', help='specify log level. ')
    parser_delete.set_defaults(func=delete_cluster)

    # list
    help_message_list = 'Show list of AWS compute clusters'
    parser_list = subparsers.add_parser('list', help=help_message_list,
                                        description=help_message_list)
    parser_list.add_argument('--log_level', help='specify log level. ')
    parser_list.set_defaults(func=list_clusters)

    # preset
    help_message_preset = 'Create a preset'
    parser_preset = subparsers.add_parser('preset', help=help_message_preset,
                                          description=help_message_preset)
    parser_preset.add_argument('--preset_name', help='specify preset name. ')
    parser_preset.add_argument('--log_level', help='specify log level. ')
    parser_preset.set_defaults(func=preset_cluster)

    return parser


def init_logger(args: argparse.Namespace, config: configparser.ConfigParser) -> None:
    '''It setups logger object.
    '''
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(logging.Formatter(LOG_STDOUT_FORMAT))
    handlers = [stdout_handler]

    # If you want to output the log to both stdout and file, remove following commments.
    # file_handler = logging.FileHandler(filename=LOG_FILE)
    # file_handler.setFormatter(logging.Formatter(LOG_FILE_FORMAT))
    # handlers = [file_handler, stdout_handler]

    logging.basicConfig(handlers=handlers)

    global log_level

    if args.log_level == 'INFO' or args.log_level == 'DEBUG':
        log_level = args.log_level
    else:
        log_level = config['default']['log_level']

    global logger
    logger = logging.getLogger(PROCESS_NAME)
    logger.setLevel(log_level)


def create_default_config() -> str:
    '''It creates default configuration files in home directory.

    Returns:
        str: configration file path.
    '''
    data_dir = os.path.expanduser('~/.cloudq/aws')
    default_dir = os.path.join(os.path.dirname(__file__), 'data')
    config_path = os.path.join(data_dir, CONFIG_FILE)

    if not os.path.isdir(data_dir):
        shutil.copytree(default_dir, data_dir)

    if not os.path.isfile(config_path):
        config_path = os.path.join(default_dir, CONFIG_FILE)

    return config_path


def create_error_message(subcommand: str) -> str:
    '''It creates of error messages for each subcommand.

    Args:
        subcommand (str): subcommand arguments
    Returns:
        str: error message.
    '''
    message = ''
    if subcommand == 'preset':
        message = MESSAGES.ERROR_MESSAGE_PRESET.value
    elif subcommand == 'create':
        message = MESSAGES.ERROR_MESSAGE_CREATE.value
    elif subcommand == 'delete':
        message = MESSAGES.ERROR_MESSAGE_DELETE.value

    return message


def main():
    '''the entry point.
    '''

    try:
        config_path = create_default_config()
        if not os.path.isfile(config_path):
            raise Exception(MESSAGES.NO_CONFIG_FILE.value.format(CONFIG_FILE))

        parser = _construct_argparser()
        args = parser.parse_args()

        config = configparser.ConfigParser()
        config.read(config_path, encoding=CONFIG_FILE_ENCODING)

        _check_config(config)
        init_logger(args, config)
        logger.info('=================== config ====================')
        show_config(config)
        logger.info('===============================================')

        start_time = time.perf_counter()
        args.func(config, args)
        elapsed_time = time.perf_counter() - start_time
        logger.debug('Process completed. {:.2f} seconds elapsed.'.format(elapsed_time))
    except Exception as e:
        message = create_error_message(args.subcommand)
        logger.error('Error: {}\n {}\n\n'.format(message, e))
        logger.error(traceback.format_exc())
        if 'parser' in locals():
            parser.print_help()


if __name__ == '__main__':
    main()
