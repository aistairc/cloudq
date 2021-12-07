# client: cloudq client command line tool
#
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
import argparse
import configparser
import json
import logging
import os
import sys
import tempfile
import traceback
import uuid
from enum import Enum

import boto3
import botocore
from pathos.multiprocessing import ProcessingPool

from .common import put_manifest, get_manifest, current_time, time_iso_to_readable, iso_to_datetime, is_finished_job, is_exist_bucket_object
from .common import MANIFEST_FILE, PROJECT_DEF_FILE, RESOURCE_DEF_FILE, STDOUT_FILE, STDERR_FILE, CANCEL_FILE, AGENT_LOG_PREFIX, JOB_STATE, MANIFEST_PARAMS, SCRIPT_TYPES

PROCESS_NAME = 'CloudQ Client'
'''Name of this process.
'''
LOG_FILE = 'cloudqcli.log'
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
    {'section': 'default',  'key': 'name',                   'type': str, 'mandatory': True},
    {'section': 'default',  'key': 'aws_profile',            'type': str, 'mandatory': True},
    {'section': 'default',  'key': 'cloudq_endpoint_url',    'type': str, 'mandatory': True},
    {'section': 'default',  'key': 'cloudq_bucket',          'type': str, 'mandatory': True},
    {'section': 'client',   'key': 'resource_profile',       'type': str, 'mandatory': False, 'default': ''},
    {'section': 'client',   'key': 'project_profile',        'type': str, 'mandatory': False, 'default': ''},
]
'''Definition of mandatory configuration parameters.
'''

MANIFEST_TEMPLATE = 'job_manifest.json'
'''File path of manifest's template.
'''

N_PARALLEL_WORKERS = 4
'''Number of worker processes that work in parallel.
'''


class MESSAGES(Enum):
    ''' List of console messages.
    '''

    # success
    SUBMIT_COMPLETED = 'Job ({}) {} has been submitted.'
    CANCEL_COMPLETED = 'Job ({}) is canceled'
    DELETE_JOB_COMPLETED = 'Job ({}) is deleted.'
    DELETE_AGENT_LOG_COMPLETED = 'Agent log ({}) is deleted.'
    FILE_DOWNLOADED = 'Saved as {}.'

    # information
    CORRUPTED_JOB_FOUND = 'The following jobs are corrupted: {}'

    # error
    CONFIG_PARAM_NOT_SPECIFIED = 'Mandatory configuration parameter is not specified: [{}] {}'
    INVALID_CONFIG_PARAM = 'Invalid configuration parameter: [{}] {} = {}'
    SCRIPT_NOT_SPECIFIED = 'Job script is not specified.'
    SCRIPT_NOT_FOUND = 'The script file is not found: {}'
    JOB_ID_NOT_SPECIFIED = 'Job ID is not specified.'
    JOB_DATA_NOT_FOUND = 'Invalid job ID: {}'
    TASK_NOT_FOUND = 'Invalid task ID: {}'
    IRREGAL_ARGUMENT_COMBINATION = 'Argument {}: not allowed with argument {}'
    LOG_NOT_FOUND = 'The log file is not exist: {}'
    JOB_ALREADY_COMPLETED = 'The job is already completed: {}'
    JOB_IS_NOT_COMPLETED = 'The job is not completed: {}'
    NO_CONFIG_FILE = 'The configuration file is not found: {}'


def submit_job(config, args, bucket):
    '''It submits a job.

    Args:
        config (configparser.ConfigParser): CloudQ CLI configuration.
        args (argparse.Namespace): Arguments for job submission.
            Used arguments are ``script``, ``hold_jid``, ``array_tid``,
             ``submit_to`` and ``submit_opt``.
        bucket (S3.Bucket): A bucket where jobs are stored.
    '''
    logger.debug('submit_job start.')
    if not args.script:
        raise Exception(MESSAGES.SCRIPT_NOT_SPECIFIED.value)
    id_ = str(uuid.uuid4())[:8]
    name = os.path.basename(args.script)

    # Upload files. key:src path value:dst path(s3)
    files = {}

    if os.path.isfile(args.script):
        files[args.script] = os.path.join(id_, name)
    else:
        raise Exception(MESSAGES.SCRIPT_NOT_FOUND.value.format(args.script))

    if not args.submit_to:
        project_def = os.path.join(DATA_DIR, config['client']['project_profile'])
        if os.path.isfile(project_def):
            files[project_def] = os.path.join(id_, PROJECT_DEF_FILE)
        resource_def = os.path.join(DATA_DIR, config['client']['resource_profile'])
        if os.path.isfile(resource_def):
            files[resource_def] = os.path.join(id_, RESOURCE_DEF_FILE)

    # Create job manifest
    manifest = json.load(open(os.path.join(DATA_DIR, MANIFEST_TEMPLATE)))
    manifest[MANIFEST_PARAMS.NAME.value] = name
    manifest[MANIFEST_PARAMS.UUID.value] = id_
    manifest[MANIFEST_PARAMS.STATE.value] = JOB_STATE.INIT.value
    manifest[MANIFEST_PARAMS.SIZE_INPUT.value] = os.path.getsize(args.script)

    if args.hold_jid:
        manifest[MANIFEST_PARAMS.HOLD_JOB_ID.value] = args.hold_jid

    if args.array_tid:
        manifest[MANIFEST_PARAMS.ARRAY_TASK_ID.value] = args.array_tid

    if args.submit_to:
        # local job
        manifest[MANIFEST_PARAMS.SCRIPT_TYPE.value] = SCRIPT_TYPES.LOCAL.value
        manifest[MANIFEST_PARAMS.SUBMIT_TO.value] = args.submit_to
        if args.submit_opt:
            manifest[MANIFEST_PARAMS.SUBMIT_OPT.value] = args.submit_opt
    else:
        # meta job
        manifest[MANIFEST_PARAMS.SCRIPT_TYPE.value] = SCRIPT_TYPES.META.value

    manifest[MANIFEST_PARAMS.TIME_SUBMIT.value] = current_time()

    # Upload files and manifest.
    for key, val in files.items():
        bucket.upload_file(key, val)

    # The manifest upload at last.
    put_manifest(bucket, id_, manifest)
    logger.info(MESSAGES.SUBMIT_COMPLETED.value.format(manifest[MANIFEST_PARAMS.UUID.value], manifest[MANIFEST_PARAMS.NAME.value]))
    logger.debug('submit_job ended.')


def stat_job(config, args, bucket):
    '''It queries status of a job.

    Args:
        config (configparser.ConfigParser): CloudQ CLI configuration.
        args (argparse.Namespace): Arguments for querying a job.
            Used argument is ``id``.
        bucket (S3.Bucket): A bucket where jobs are stored.
    '''
    logger.debug('stat_job start.')
    if not args.id:
        raise Exception(MESSAGES.JOB_ID_NOT_SPECIFIED.value)
    s3file = os.path.join(args.id, MANIFEST_FILE)
    fd, tmpfile = tempfile.mkstemp()
    try:
        bucket.download_file(s3file, tmpfile)
    except botocore.exceptions.ClientError:
        raise Exception(MESSAGES.JOB_DATA_NOT_FOUND.value.format(args.id))

    with open(tmpfile, 'r') as f:
        stat = json.load(f)
        keylen = max(len(key) for key in stat.keys())
        template = '{{:<{}}}  {{:<}}'.format(keylen)
        for key, val in stat.items():
            if key.startswith('time_') and val:
                val = time_iso_to_readable(val)
            logger.info(template.format(key, val))
    os.remove(tmpfile)
    logger.debug('stat_job ended.')


def show_job_log(config, args, bucket):
    '''It shows standard output of a job on console.

    Args:
        config (configparser.ConfigParser): CloudQ CLI configuration.
        args (argparse.Namespace): Arguments for querying a job.
            Used argument are ``id``, ``tid``, ``agent`` and ``error``.
        bucket (S3.Bucket): A bucket where jobs are stored.
    '''
    logger.debug('show_job_log start.')
    if (args.agent) and (args.error):
        raise Exception(MESSAGES.IRREGAL_ARGUMENT_COMBINATION.value.format('--agent', '--error'))
    if (args.agent) and (args.tid):
        raise Exception(MESSAGES.IRREGAL_ARGUMENT_COMBINATION.value.format('--agent', '--tid'))

    s3files = {}
    if args.id:
        if not is_exist_bucket_object(bucket, args.id):
            raise Exception(MESSAGES.JOB_DATA_NOT_FOUND.value.format(args.id))
        if args.error:
            filename = STDERR_FILE
        else:
            filename = STDOUT_FILE

        if args.tid:
            s3files[''] = os.path.join(args.id, '{}.{}'.format(filename, args.tid))
            if not is_exist_bucket_object(bucket, s3files['']):
                raise Exception(MESSAGES.TASK_NOT_FOUND.value.format(args.tid))
        else:
            objects = bucket.objects.filter(Prefix=os.path.join(args.id, filename))
            for object in objects:
                pos = object.key.find('.')
                if pos >= 0:
                    tid = object.key[pos+1:]
                else:
                    tid = ''
                s3files[tid] = object.key

    elif args.agent:
        s3files[''] = os.path.join(AGENT_LOG_PREFIX, args.agent)
        if not is_exist_bucket_object(bucket, s3files['']):
            raise Exception(MESSAGES.LOG_NOT_FOUND.value.format(args.agent))

    for key, val in s3files.items():
        if is_exist_bucket_object(bucket, val):
            fd, tmpfile = tempfile.mkstemp()
            try:
                bucket.download_file(val, tmpfile)
            except botocore.exceptions.ClientError:
                pass

            with open(tmpfile, 'r') as f:
                if len(key) > 0:
                    logger.info('==================== task {} ===================='.format(key))
                logger.info(f.read())
            os.remove(tmpfile)
    logger.debug('show_job_log ended.')


def cancel_job(config, args, bucket):
    '''It cancels a waiting/running job.

    It cancels a job if the job is not completed.

    Args:
        config (configparser.ConfigParser): CloudQ CLI configuration.
        args (argparse.Namespace): Arguments for querying a job.
            Used arguments are ``id``.
        bucket (S3.Bucket): A bucket where jobs are stored.
    '''
    logger.debug('cancel_job start.')
    if not args.id:
        raise Exception(MESSAGES.JOB_ID_NOT_SPECIFIED.value)
    id_ = args.id
    manifest = get_manifest(bucket, id_)
    if manifest is None:
        raise Exception(MESSAGES.JOB_DATA_NOT_FOUND.value.format(id_))

    if not is_finished_job(manifest):
        s3file = os.path.join(id_, CANCEL_FILE)
        if not is_exist_bucket_object(bucket, s3file):
            fd, tmpfile = tempfile.mkstemp()
            with open(tmpfile, 'w') as fp:
                fp.write('')

            bucket.upload_file(tmpfile, s3file)
            os.remove(tmpfile)
        logger.info(MESSAGES.CANCEL_COMPLETED.value.format(id_))
    else:
        raise Exception(MESSAGES.JOB_ALREADY_COMPLETED.value.format(id_))
    logger.debug('cancel_job ended.')


def del_job(config, args, bucket):
    '''It deletes a completed job from CloudQ.

    It deletes a job if the job is in completed.

    Args:
        config (configparser.ConfigParser): CloudQ CLI configuration.
        args (argparse.Namespace): Arguments for querying a job.
            Used arguments are ``id``, ``agent``, ``all``.
        bucket (S3.Bucket): A bucket where jobs are stored.
    '''
    logger.debug('del_job start.')
    if args.id:
        id_ = args.id
        manifest = get_manifest(bucket, id_)
        if manifest is None:
            raise Exception(MESSAGES.JOB_DATA_NOT_FOUND.value.format(id_))

        if is_finished_job(manifest):
            bucket.objects.filter(Prefix=id_ + '/').delete()
            logger.info(MESSAGES.DELETE_JOB_COMPLETED.value.format(id_))
        else:
            raise Exception(MESSAGES.JOB_IS_NOT_COMPLETED.value.format(id_))
    elif args.agent:
        s3file = os.path.join(AGENT_LOG_PREFIX, args.agent)
        if not is_exist_bucket_object(bucket, s3file):
            raise Exception(MESSAGES.LOG_NOT_FOUND.value.format(args.agent))
        bucket.objects.filter(Prefix=s3file).delete()
        logger.info(MESSAGES.DELETE_AGENT_LOG_COMPLETED.value.format(args.agent))
    elif args.all:
        # get job informations
        jobs = _get_jobs(config, bucket)
        jobs_valid = [job[1] for job in jobs if job[0] and is_finished_job(job[1])]
        for job in jobs_valid:
            bucket.objects.filter(Prefix=job[MANIFEST_PARAMS.UUID.value] + '/').delete()
            logger.info(MESSAGES.DELETE_JOB_COMPLETED.value.format(job[MANIFEST_PARAMS.UUID.value]))
    logger.debug('del_job ended.')


def _get_jobs(config, bucket):
    def _task_assign(jids, n_workers):
        '''Returns:
            list[list[str]]: List of job ID.
        '''
        lst_jids = [[] for _ in range(n_workers)]
        idx = 0
        for jid in jids:
            lst_jids[idx].append(jid)
            idx = (idx + 1) % n_workers
        return [x for x in lst_jids if x]

    def _list_manifests(jids):
        return [_job_manifest(jid) for jid in jids if not jid == AGENT_LOG_PREFIX]

    def _job_manifest(jid):
        '''Returns:
            (bool: dict[str, obj]): bool is True if the job ID is valid.
                dict[str, obj] is the manifest of the job.
        '''
        _bucket = _get_bucket(config)
        manifest = get_manifest(_bucket, jid)
        if manifest is None:
            return False, {MANIFEST_PARAMS.UUID.value: jid}
        return True, manifest

    def _flat_jobs(lst_jobs):
        flat_jobs = []
        for jobs in lst_jobs:
            for job in jobs:
                # Missing parameters replace to empty string.
                for key in [MANIFEST_PARAMS.UUID.value,
                            MANIFEST_PARAMS.NAME.value,
                            MANIFEST_PARAMS.STATE.value,
                            MANIFEST_PARAMS.RUN_SYSTEM.value,
                            MANIFEST_PARAMS.TIME_SUBMIT.value,
                            MANIFEST_PARAMS.TIME_START.value,
                            MANIFEST_PARAMS.TIME_FINISH.value]:
                    if key not in job[1]:
                        job[1][key] = ''
                flat_jobs.append(job)
        return flat_jobs

    jids = {k.key.split('/')[0] for k in bucket.objects.filter()}
    lst_jids = _task_assign(jids, N_PARALLEL_WORKERS)
    pool = ProcessingPool(nodes=N_PARALLEL_WORKERS)
    lst_jobs = pool.map(lambda jids: _list_manifests(jids), lst_jids)
    return _flat_jobs(lst_jobs)


def list_jobs(config, args, bucket):
    '''It shows waiting/running jobs in CloudQ.

    Args:
        config (configparser.ConfigParser): CloudQ CLI configuration.
        args (argparse.Namespace): Arguments for querying a job.
        bucket (S3.Bucket): A bucket where jobs are stored.
    '''
    logger.debug('list_jobs start.')
    # get job informations
    jobs = _get_jobs(config, bucket)

    # output valid jobs
    output_format = '{:>12s}  {:>20s}  {:>8s}  {:>10s}  {:>19s}'
    colmuns = ['job-ID', 'name', 'state', 'run-system', 'submit at']
    header = output_format.format(*colmuns)
    logger.info(header)
    logger.info('-' * len(header))
    jobs_valid = [job[1] for job in jobs if job[0] and not is_finished_job(job[1])]
    jobs_valid.sort(key=lambda x: iso_to_datetime(x[MANIFEST_PARAMS.TIME_SUBMIT.value]))
    for job in jobs_valid:
        logger.info(output_format.format(job[MANIFEST_PARAMS.UUID.value][:12],
                                         job[MANIFEST_PARAMS.NAME.value][:20],
                                         job[MANIFEST_PARAMS.STATE.value],
                                         job[MANIFEST_PARAMS.RUN_SYSTEM.value][:10],
                                         time_iso_to_readable(job[MANIFEST_PARAMS.TIME_SUBMIT.value])))

    # output invalid jobs
    jobs_invalid = [job[1] for job in jobs if not job[0]]
    if jobs_invalid:
        ijids = [job[MANIFEST_PARAMS.UUID.value] for job in jobs_invalid]
        logger.info('')
        logger.info(MESSAGES.CORRUPTED_JOB_FOUND.value.format(', '.join(ijids)))
    logger.debug('list_jobs ended.')


def history_jobs(config, args, bucket):
    '''It shows completed jobs in CloudQ.

    Args:
        config (configparser.ConfigParser): CloudQ CLI configuration.
        args (argparse.Namespace): Arguments for querying a job.
        bucket (S3.Bucket): A bucket where jobs are stored.
    '''
    logger.debug('history_jobs start.')
    # get job informations
    jobs = _get_jobs(config, bucket)

    # output valid jobs
    output_format = '{:>12s}  {:>20s}  {:>8s}  {:>10s}  {:>19s}  {:>19s}  {:>19s}'
    colmuns = ['job-ID', 'name', 'state', 'run-system', 'submit at', 'start at', 'finish at']
    header = output_format.format(*colmuns)
    logger.info(header)
    logger.info('-' * len(header))
    jobs_valid = [job[1] for job in jobs if job[0] and is_finished_job(job[1])]
    jobs_valid.sort(key=lambda x: iso_to_datetime(x[MANIFEST_PARAMS.TIME_SUBMIT.value]))
    for job in jobs_valid:
        logger.info(output_format.format(job[MANIFEST_PARAMS.UUID.value][:12],
                                         job[MANIFEST_PARAMS.NAME.value][:20],
                                         job[MANIFEST_PARAMS.STATE.value],
                                         job[MANIFEST_PARAMS.RUN_SYSTEM.value][:10],
                                         time_iso_to_readable(job[MANIFEST_PARAMS.TIME_SUBMIT.value]),
                                         time_iso_to_readable(job[MANIFEST_PARAMS.TIME_START.value]),
                                         time_iso_to_readable(job[MANIFEST_PARAMS.TIME_FINISH.value])))

    # output invalid jobs
    jobs_invalid = [job[1] for job in jobs if not job[0]]
    if jobs_invalid:
        ijids = [job[MANIFEST_PARAMS.UUID.value] for job in jobs_invalid]
        logger.info('')
        logger.info(MESSAGES.CORRUPTED_JOB_FOUND.value.format(', '.join(ijids)))
    logger.debug('history_jobs ended.')


def stageout(config, args, bucket):
    '''It downloads specified job's objects.

    Args:
        config (configparser.ConfigParser): CloudQ CLI configuration.
        args (argparse.Namespace): Arguments for querying a job.
            Used argument is ``id``.
        bucket (S3.Bucket): A bucket where jobs are stored.
    '''
    logger.debug('stageout start.')
    if not args.id:
        raise Exception(MESSAGES.JOB_ID_NOT_SPECIFIED.value)
    prefix = args.id + '/'
    if not is_exist_bucket_object(bucket, prefix):
        raise Exception(MESSAGES.JOB_DATA_NOT_FOUND.value.format(args.id))
    try:
        os.makedirs(args.id, exist_ok=True)
        for obj in bucket.objects.filter(Prefix=prefix):
            outfile = os.path.join(args.id, os.path.basename(obj.key))
            bucket.download_file(obj.key, outfile)
        logger.info(MESSAGES.FILE_DOWNLOADED.value.format(args.id))
    except botocore.exceptions.ClientError:
        logger.error(MESSAGES.JOB_DATA_NOT_FOUND.value.format(args.id))
    logger.debug('stageout ended.')


def _get_bucket(config):
    endpoint_url = config['default']['cloudq_endpoint_url']
    aws_profile = config['default']['aws_profile']
    root_bucket = config['default']['cloudq_bucket']

    session = boto3.Session(profile_name=aws_profile)
    s3 = session.resource('s3', endpoint_url=endpoint_url)
    return s3.Bucket(root_bucket)


def _check_config(config):
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
                    raise Exception(MESSAGES.INVALID_CONFIG_PARAM.value.format(param['section'], param['key'], '(empty)'))

            elif param['type'] is int:
                # integer parameter
                value = config.getint(param['section'], param['key'])
                if param['min'] > value:
                    raise Exception(MESSAGES.INVALID_CONFIG_PARAM.value.format(param['section'], param['key'], value))

        except configparser.NoOptionError:
            if param['mandatory']:
                # if this parameter is mandatory, raise exception.
                raise Exception(MESSAGES.CONFIG_PARAM_NOT_SPECIFIED.value.format(param['section'], param['key']))
            else:
                # if this parameter is optional, set detault value.
                config[param['section']][param['key']] = param['default']


def _construct_argparser():
    parser = argparse.ArgumentParser(description='CloudQ command line tool', add_help=True)
    subparsers = parser.add_subparsers(dest='subcommand')
    subparsers.required = True

    # submit
    help_message_submit = 'Submit a job'
    parser_submit = subparsers.add_parser('submit', help=help_message_submit,
                                          description=help_message_submit)
    parser_submit.add_argument('--script', help='job script')
    parser_submit.add_argument('--hold_jid', help='specify dependent jobs. ')
    parser_submit.add_argument('--array_tid', help='specify tasks to perform in an array job. ')
    parser_submit.add_argument('--submit_to', help='specify a system where the job script runs. '
                               'Available only to local job script')
    parser_submit.add_argument('--submit_opt', help='specify a command line arguments of job '
                               'submission command.  Available only to local job script')
    parser_submit.set_defaults(func=submit_job)

    # stat
    help_message_stat = 'Show the status of a job'
    parser_stat = subparsers.add_parser('stat', help=help_message_stat,
                                        description=help_message_stat)
    parser_stat.add_argument('--id', help='job id')
    parser_stat.set_defaults(func=stat_job)

    # log
    help_message_log = 'Show the standard output/error of a job'
    desc_message_log = help_message_log + '. ' + 'By default, it shows the standard output.'
    parser_log = subparsers.add_parser('log', help=help_message_log, description=desc_message_log)
    ex_group_log = parser_log.add_mutually_exclusive_group(required=True)
    ex_group_log.add_argument('--id', help='job id')
    ex_group_log.add_argument('--agent', help='agent name')
    parser_log.add_argument('--tid',
                            help='task id. It can specifies only when the job is array-job')
    parser_log.add_argument('--error',
                            help='show the standard error, instead of standard output',
                            action='store_true')
    parser_log.set_defaults(func=show_job_log)

    # cancel
    help_message_cancel = 'Cancel a job'
    parser_cancel = subparsers.add_parser('cancel', help=help_message_cancel, description=help_message_cancel)
    parser_cancel.add_argument('--id', help='job id')
    parser_cancel.set_defaults(func=cancel_job)

    # delete
    help_message_del = 'Delete a job'
    parser_del = subparsers.add_parser('delete', help=help_message_del, description=help_message_del)
    ex_group_del = parser_del.add_mutually_exclusive_group(required=True)
    ex_group_del.add_argument('--id', help='job id')
    ex_group_del.add_argument('--agent', help='agent name')
    ex_group_del.add_argument('--all', help='delete all completed jobs', action='store_true')
    parser_del.set_defaults(func=del_job)

    # stage out
    help_message_stageout = 'Download outputs of a job'
    parser_stageout = subparsers.add_parser('stageout', help=help_message_stageout,
                                            description=help_message_stageout)
    parser_stageout.add_argument('--id', help='job id')
    parser_stageout.set_defaults(func=stageout)

    # list
    help_message_list = 'Show list of waiting/running jobs'
    parser_list = subparsers.add_parser('list', help=help_message_list,
                                        description=help_message_list)
    parser_list.set_defaults(func=list_jobs)

    # history
    help_message_history = 'Show list of completed jobs'
    parser_history = subparsers.add_parser('history', help=help_message_history,
                                           description=help_message_history)
    parser_history.set_defaults(func=history_jobs)

    return parser


def init_logger():
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(logging.Formatter(LOG_STDOUT_FORMAT))
    handlers = [stdout_handler]

    # If you want to output the log to both stdout and file, remove following commments.
    # file_handler = logging.FileHandler(filename=LOG_FILE)
    # file_handler.setFormatter(logging.Formatter(LOG_FILE_FORMAT))
    # handlers = [file_handler, stdout_handler]

    logging.basicConfig(handlers=handlers)

    global logger
    logger = logging.getLogger(PROCESS_NAME)
    logger.setLevel(logging.DEBUG)


def main():
    init_logger()

    try:
        global DATA_DIR
        DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')

        if not os.path.isfile(os.path.join(DATA_DIR, CONFIG_FILE)):
            raise Exception(MESSAGES.NO_CONFIG_FILE.value.format(CONFIG_FILE))

        config = configparser.ConfigParser()
        config.read(os.path.join(DATA_DIR, CONFIG_FILE), encoding=CONFIG_FILE_ENCODING)

        parser = _construct_argparser()
        args = parser.parse_args()

        _check_config(config)

        bucket = _get_bucket(config)

        args.func(config, args, bucket)
    except Exception as e:
        logger.error('Error: {}\n\n'.format(e))
        logger.debug(traceback.format_exc())
        if 'parser' in locals():
            parser.print_help()


if __name__ == '__main__':
    main()
