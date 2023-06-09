# agent: cloudq agent
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
import argparse
import configparser
import datetime
import glob
import logging
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
from enum import Enum
import boto3
from concurrent.futures import ThreadPoolExecutor
from .common import (get_manifest, put_manifest, current_time, iso_to_datetime,
                     is_exist_bucket_object, is_finished_job)
from .common import (STAGEOUT_FILE, CANCEL_FILE, PROJECT_DEF_FILE,
                     RESOURCE_DEF_FILE, AGENT_LOG_PREFIX)
from .common import JOB_STATE, MANIFEST_PARAMS, SCRIPT_TYPES
from .interface import JobManagerAccessor
from .interface import MetaJobScriptConverterAccessor

PROCESS_NAME = 'CloudQ Agent'
'''Name of this process.
'''
LOG_FILE = 'cloudqd.log'
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
PATTERN_LOG_FILE = r'std(out|err)\S*$'
'''Regular expression pattern of stdout/stderr files.
'''

CONFIG_PARAMS = [
    {'section': 'default',  'key': 'name',
     'type': str, 'mandatory': True},
    {'section': 'default',  'key': 'aws_profile',
     'type': str, 'mandatory': True},
    {'section': 'default',  'key': 'cloudq_endpoint_url',
     'type': str, 'mandatory': True},
    {'section': 'default',  'key': 'cloudq_bucket',
     'type': str, 'mandatory': True},
    {'section': 'default',  'key': 'log_level',
     'type': str, 'mandatory': False,  'default': 'INFO'},
    {'section': 'agent',    'key': 'type',
     'type': str, 'mandatory': True},
    {'section': 'agent',    'key': 'num_procs',
     'type': int, 'mandatory': False,  'default': 8,    'min': 1},
    {'section': 'agent',    'key': 'daemon_interval',
     'type': int, 'mandatory': False,  'default': 5,    'min': 1},
    {'section': 'agent',    'key': 'cloudq_directory',
     'type': str, 'mandatory': False,  'default': '~/.cloudq'},
]
'''Definition of mandatory configuration parameters.
'''


class MESSAGES(Enum):
    ''' List of console messages.
    '''

    # success
    # SUBMIT_COMPLETED = 'Job ({}) {} has been submitted.'

    # information
    META_JOB_CONVERTED = 'Meta job script {}'
    JOB_RECEIVED = 'submit job: job ({}) received.'
    JOB_SUBMITTED = 'submit job: job({}) is submitted. local-jobid:{}'
    JOB_SUBMISSION_FAILED = 'submit job: Failed to submit job ({})'
    JOB_UPDATED = 'stat job: job({}) is updated. status:{}'
    JOB_FINISHED = 'stat job: job ({}) is finished'
    JOB_ERROR_OCCURRED = 'stat job: Error occurred to job ({})'
    JOB_TIMEDOUT = 'stat job: job ({}) timed out'
    JOB_DELETED = 'stat job: job ({}) deleted'
    JOB_CANCELED = 'cancel job: job({}) is canceled.'
    JOB_FORCIBLY_CANCELED = 'cancel job: job({}) is forcibly canceled.'

    # error
    CONFIG_PARAM_NOT_SPECIFIED = 'Mandatory configuration parameter is not specified: [{}] {}'
    INVALID_CONFIG_PARAM = 'Invalid configuration parameter: [{}] {} = {}'
    NO_CONFIG_FILE = 'The configuration file is not found: {}'
    INVALID_CACHE_DIR_PATH = 'Failed to create cache directory: {}'
    NO_SCRIPT_FILE = 'The script file is not found: {}'


root_dir = None
'''Root directory path of cloudQ agent.
'''

cache_dir = None
'''Path to CloudQ working directory.
'''

logger = None
'''The logger object
'''

job_manager = None
'''The object of job manager accessor.
'''

meta_job_converter = None
'''The object of meta job script converter accessor.
'''

thread_pool = None
'''The object of thread pool.
'''


def submit_job(bucket: object, id_: str, manifest: dict) -> bool:
    '''It submits a job to the local scheduler.

    Args:
        bucket (S3.Bucket): A bucket where the job is stored.
        id_ (str): Job ID.
        manifest dict[str: obj]: A job manifest.
    Returns:
        bool: If the job is submitted, returns True.
    '''
    logger.debug('submit_job start. id:{}'.format(id_))
    logger.info('submit job: start. id:{}'.format(id_))
    system_name = config['default']['name'].lower()
    if manifest[MANIFEST_PARAMS.SCRIPT_TYPE.value] == SCRIPT_TYPES.LOCAL.value:
        run_system = manifest[MANIFEST_PARAMS.SUBMIT_TO.value].lower()
        if run_system != system_name:
            logger.debug('submit_job ended. id:{}  (Other system\'s job.)'.format(id_))
            logger.info('submit job: not processed. id:{}  (Other system\'s job.)'.format(id_))
            return False

    # check hold job.
    if MANIFEST_PARAMS.HOLD_JOB_ID.value in manifest:
        hold_jids = manifest[MANIFEST_PARAMS.HOLD_JOB_ID.value]
        if len(hold_jids) > 0:
            logger.info('submit job: check hold jods: {}'.format(hold_jids))
            for hold_jid in hold_jids.split(','):
                hold_manifest = get_manifest(bucket, hold_jid.strip())
                if hold_manifest:
                    if not is_finished_job(hold_manifest):
                        logstr = 'submit_job ended. id:{}  (Hold jod({}) is not finished.)'
                        logger.debug(logstr.format(id_, hold_jid))
                        logstr = 'submit job: not processed. id:{}  (Hold jod({}) is not finished.)'
                        logger.info(logstr.format(id_, hold_jid))
                        return False
            logger.info('submit job: hold jods are finished.')

    try:
        manifest[MANIFEST_PARAMS.TIME_RECEIVE.value] = current_time()
        manifest[MANIFEST_PARAMS.RUN_SYSTEM.value] = system_name

        proc = subprocess.Popen('whoami', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (out, err) = proc.communicate()
        manifest[MANIFEST_PARAMS.LOCAL_ACCOUNT.value] = out.decode().strip()

        name = manifest[MANIFEST_PARAMS.NAME.value]
        logger.info(MESSAGES.JOB_RECEIVED.value.format(id_))

        workdir = os.path.join(cache_dir, id_)
        os.makedirs(workdir, exist_ok=True)
        os.chdir(workdir)
        manifest[MANIFEST_PARAMS.WORK_DIR.value] = workdir

        s3file = os.path.join(id_, name)
        if not is_exist_bucket_object(bucket, s3file):
            raise Exception(MESSAGES.NO_SCRIPT_FILE.value.format(name))
        bucket.download_file(s3file, name)

        # convert meta job script to local job script.
        if not manifest[MANIFEST_PARAMS.SCRIPT_TYPE.value] == SCRIPT_TYPES.LOCAL.value:
            bucket.download_file(os.path.join(id_, PROJECT_DEF_FILE), PROJECT_DEF_FILE)
            bucket.download_file(os.path.join(id_, RESOURCE_DEF_FILE), RESOURCE_DEF_FILE)
            result = meta_job_converter.to_local_job_script(
                manifest, config['default']['cloudq_endpoint_url'],
                config['default']['aws_profile'])
            if result:
                manifest = result
            else:
                remove_work_dir(manifest)
                logger.debug('submit_job ended. id:{}  (Other system\'s job.)'.format(id_))
                logger.info('submit job: not processed. id:{}  (Other system\'s job.)'.format(id_))
                return False
            local_script = manifest[MANIFEST_PARAMS.LOCAL_NAME.value]
            s3file = os.path.join(id_, local_script)
            bucket.upload_file(local_script, s3file)
            logger.info(MESSAGES.META_JOB_CONVERTED.value.format(id_))

        manifest = job_manager.submit_job(manifest)
    except Exception as e:
        manifest[MANIFEST_PARAMS.ERROR_MSG.value] = str(e)
        logger.error('Error({}): {}\n\n'.format(id_, e))
        logger.error(traceback.format_exc())

    if manifest[MANIFEST_PARAMS.JOB_ID.value]:
        logger.info(MESSAGES.JOB_SUBMITTED.value.format(
            id_, manifest[MANIFEST_PARAMS.JOB_ID.value]))
        manifest[MANIFEST_PARAMS.STATE.value] = JOB_STATE.READY.value
        manifest[MANIFEST_PARAMS.TIME_READY.value] = current_time()
    else:
        logger.info(MESSAGES.JOB_SUBMISSION_FAILED.value.format(id_))
        manifest[MANIFEST_PARAMS.STATE.value] = JOB_STATE.ERROR.value
        manifest[MANIFEST_PARAMS.TIME_FINISH.value] = current_time()
        remove_work_dir(manifest)

    put_manifest(bucket, id_, manifest)
    logger.debug('submit_job ended. id:{}'.format(id_))
    return True


def upload_logs(bucket: object, manifest: dict) -> None:
    '''It uploads standard output and error of a job to an object storage.

    Args:
        bucket (S3.Bucket): A bucket where the job is stored.
        manifest (dict[str: obj]): A job manifest.
    '''
    id_ = manifest[MANIFEST_PARAMS.UUID.value]
    workdir = manifest[MANIFEST_PARAMS.WORK_DIR.value]
    # name = manifest[MANIFEST_PARAMS.NAME.value]
    # jobid = manifest[MANIFEST_PARAMS.JOB_ID.value]
    if not workdir:
        return

    manifest = job_manager.get_job_log(manifest, True)
    manifest = job_manager.get_job_log(manifest, False)

    for src in [p for p in glob.glob(os.path.join(workdir, '*')) if re.search(PATTERN_LOG_FILE, p)]:
        s3file = os.path.join(id_, os.path.basename(src))
        bucket.upload_file(src, s3file)
        logger.debug('log uploaded. file:{}'.format(s3file))


def stageout_file(bucket: object, manifest: dict) -> None:
    '''It uploads job outputs to an object storage.

    Args:
        bucket (S3.Bucket): A bucket where the job is stored.
        manifest (dict[str: obj]): A job manifest.
    '''
    id_ = manifest[MANIFEST_PARAMS.UUID.value]
    workdir = manifest[MANIFEST_PARAMS.WORK_DIR.value]
    if not workdir or not os.path.isdir(workdir):
        logger.debug('no stageout files. workdir:{}'.format(workdir))
        return

    basename = os.path.join(cache_dir, id_ + '-output')
    zipfile = basename + '.zip'
    shutil.make_archive(basename, 'zip', root_dir=workdir)

    manifest[MANIFEST_PARAMS.SIZE_OUTPUT.value] = os.path.getsize(zipfile)
    s3file = os.path.join(id_, STAGEOUT_FILE)
    bucket.upload_file(zipfile, s3file)
    logger.debug('output data uploaded. file:{}'.format(s3file))
    os.remove(zipfile)


def stat_job(bucket: object, id_: str, manifest: dict) -> None:
    '''It queries status of a job.

    Args:
        bucket (S3.Bucket): A bucket where the job is stored.
        id_ (str): Job ID.
        manifest dict[str: obj]: A job manifest.
    '''
    logger.debug('stat_job start. id:{}'.format(id_))
    logger.info('stat job: start. id:{}'.format(id_))
    jobs = job_manager.get_jobs_status()

    # update job's state
    for j in jobs:
        updated = False
        if j[0] != manifest[MANIFEST_PARAMS.JOB_ID.value]:
            continue

        if (j[1] == JOB_STATE.RUN.value and
                manifest[MANIFEST_PARAMS.STATE.value] != JOB_STATE.RUN.value):
            manifest[MANIFEST_PARAMS.STATE.value] = JOB_STATE.RUN.value
            manifest[MANIFEST_PARAMS.TIME_START.value] = current_time()
            updated = True
        elif (j[1] == JOB_STATE.READY.value and
              manifest[MANIFEST_PARAMS.STATE.value] == JOB_STATE.INIT.value):
            manifest[MANIFEST_PARAMS.STATE.value] = JOB_STATE.READY.value
            manifest[MANIFEST_PARAMS.TIME_READY.value] = current_time()
            updated = True
        elif (j[1] == JOB_STATE.DELETING.value and
              manifest[MANIFEST_PARAMS.STATE.value] != JOB_STATE.DELETING.value):
            manifest[MANIFEST_PARAMS.STATE.value] = JOB_STATE.DELETING.value
            updated = True
        elif (j[1] == JOB_STATE.COMPLETING.value and
              manifest[MANIFEST_PARAMS.STATE.value] != JOB_STATE.COMPLETING.value):
            manifest[MANIFEST_PARAMS.STATE.value] = JOB_STATE.COMPLETING.value
            updated = True
        elif (j[1] == JOB_STATE.ERROR.value and
              manifest[MANIFEST_PARAMS.STATE.value] != JOB_STATE.ERROR.value):
            manifest[MANIFEST_PARAMS.STATE.value] = JOB_STATE.ERROR.value
            manifest[MANIFEST_PARAMS.TIME_FINISH.value] = current_time()
            updated = True
        elif (j[1] == JOB_STATE.DELETED.value and
              manifest[MANIFEST_PARAMS.STATE.value] != JOB_STATE.DELETED.value):
            manifest[MANIFEST_PARAMS.STATE.value] = JOB_STATE.DELETED.value
            manifest[MANIFEST_PARAMS.TIME_FINISH.value] = current_time()
            updated = True
        elif (j[1] == JOB_STATE.TIMEOUT.value and
              manifest[MANIFEST_PARAMS.STATE.value] != JOB_STATE.TIMEOUT.value):
            manifest[MANIFEST_PARAMS.STATE.value] = JOB_STATE.TIMEOUT.value
            manifest[MANIFEST_PARAMS.TIME_FINISH.value] = current_time()
            updated = True

        if updated:
            logger.info(MESSAGES.JOB_UPDATED.value.format(id_, j[1]))
            put_manifest(bucket, id_, manifest)
            upload_logs(bucket, manifest)
            if (manifest[MANIFEST_PARAMS.STATE.value] in
                    (JOB_STATE.ERROR.value, JOB_STATE.DELETED.value, JOB_STATE.TIMEOUT.value)):
                remove_work_dir(manifest)
                if manifest[MANIFEST_PARAMS.STATE.value] == JOB_STATE.ERROR.value:
                    logger.info(MESSAGES.JOB_ERROR_OCCURRED.value.format(id_))
                if manifest[MANIFEST_PARAMS.STATE.value] == JOB_STATE.DELETED.value:
                    logger.info(MESSAGES.JOB_DELETED.value.format(id_))
                if manifest[MANIFEST_PARAMS.STATE.value] == JOB_STATE.TIMEOUT.value:
                    logger.info(MESSAGES.JOB_TIMEDOUT.value.format(id_))
        elif manifest[MANIFEST_PARAMS.STATE.value] == JOB_STATE.RUN.value:
            upload_logs(bucket, manifest)

        logger.debug('stat_job ended. id:{}'.format(id_))
        logger.info('stat job: succeeded. id:{}'.format(id_))
        return

    # job is already finished.
    if (manifest[MANIFEST_PARAMS.STATE.value] in
            (JOB_STATE.RUN.value, JOB_STATE.READY.value, JOB_STATE.DELETING.value,
             JOB_STATE.COMPLETING.value)):
        manifest[MANIFEST_PARAMS.TIME_SO_START.value] = current_time()
        stageout_file(bucket, manifest)
        manifest[MANIFEST_PARAMS.TIME_SO_FINISH.value] = current_time()
        manifest[MANIFEST_PARAMS.STATE.value] = JOB_STATE.DONE.value
        manifest[MANIFEST_PARAMS.TIME_FINISH.value] = current_time()
        put_manifest(bucket, id_, manifest)
        upload_logs(bucket, manifest)
        remove_work_dir(manifest)
        logger.info(MESSAGES.JOB_FINISHED.value.format(id_))

        logger.debug('stat_job ended. id:{}'.format(id_))
        return
    logger.debug('stat_job ended. id:{}'.format(id_))


def cancel_job(bucket: object, id_: str, manifest: dict) -> None:
    '''It cancels a job.

    Args:
        bucket (S3.Bucket): A bucket where the job is stored.
        id_ (str): Job ID.
        manifest dict[str: obj]: A job manifest.
    '''
    logger.debug('cancel_job start. id:{}'.format(id_))
    logger.info('cancel job: start. id:{}'.format(id_))

    if manifest[MANIFEST_PARAMS.STATE.value] == JOB_STATE.INIT.value:
        manifest[MANIFEST_PARAMS.STATE.value] = JOB_STATE.DELETED.value
        manifest[MANIFEST_PARAMS.TIME_FINISH.value] = current_time()
        put_manifest(bucket, id_, manifest)
        remove_work_dir(manifest)
        logger.info(MESSAGES.JOB_FINISHED.value.format(id_))
        logger.debug('cancel_job ended. id:{}'.format(id_))
        return

    jobs = job_manager.get_jobs_status()
    job_exists = False
    for job in jobs:
        if manifest[MANIFEST_PARAMS.JOB_ID.value] in job[0]:
            job_exists = True
            break

    if not job_exists:
        logger.debug('cancel_job ended (The job is already finished). id:{}'.format(id_))
        logger.info('cancel job: not processed (The job is already finished). id:{}'.format(id_))
        return

    os.chdir(manifest[MANIFEST_PARAMS.WORK_DIR.value])

    s3file = os.path.join(id_, CANCEL_FILE)
    bucket.download_file(s3file, CANCEL_FILE)
    with open(CANCEL_FILE, 'r') as f:
        cancel_file_str = f.read()

    if len(cancel_file_str) > 0:
        if (datetime.datetime.now(datetime.timezone.utc) >=
                iso_to_datetime(cancel_file_str) + datetime.timedelta(seconds=60)):
            logger.debug('cancel job (force): id:{}'.format(id_))
            manifest = job_manager.cancel_job(manifest, True)
            manifest[MANIFEST_PARAMS.STATE.value] = JOB_STATE.DONE.value
            logger.info(MESSAGES.JOB_FORCIBLY_CANCELED.value.format(id_))
            updated = True
        else:
            logger.debug('Waiting for the job to delete: id={}'.format(id_))
            updated = False
    else:
        logger.debug('cancel job (normal): id={}'.format(id_))
        manifest = job_manager.cancel_job(manifest, False)
        manifest[MANIFEST_PARAMS.STATE.value] = JOB_STATE.DELETING.value
        with open(CANCEL_FILE, 'w') as f:
            canceled_time = current_time()
            logger.debug('The job({}) is canceled at {}'.format(id_, canceled_time))
            f.write(canceled_time)
        bucket.upload_file(CANCEL_FILE, s3file)
        logger.info(MESSAGES.JOB_CANCELED.value.format(id_))
        updated = True

    if updated:
        put_manifest(bucket, id_, manifest)

    logger.debug('cancel_job ended. id:{}'.format(id_))
    logger.info('cancel job: succeeded. id:{}'.format(id_))


def remove_work_dir(manifest: dict) -> None:
    '''It removes a work directory.

    Args:
        manifest dict[str: obj]: A job manifest.
    '''
    work_dir = manifest[MANIFEST_PARAMS.WORK_DIR.value]
    if os.path.isdir(work_dir):
        logger.info('The working directory is removed:{}'.format(work_dir))
        shutil.rmtree(work_dir)


def checknrun() -> None:
    '''It process jobs in an object storage.
    '''
    logger.debug('checknrun start.')
    endpoint_url = config['default']['cloudq_endpoint_url']
    root_bucket = config['default']['cloudq_bucket']
    aws_profile = config['default']['aws_profile']

    def _process_job(jid: str) -> None:
        try:
            os.chdir(root_dir)

            _session = boto3.Session(profile_name=aws_profile)
            _s3 = _session.resource('s3', endpoint_url=endpoint_url)
            _bucket = _s3.Bucket(root_bucket)
            manifest = get_manifest(_bucket, jid)
            if manifest is None:
                logger.info('[{}] manifest is None.'.format(jid))
                return
            if MANIFEST_PARAMS.RUN_SYSTEM.value in manifest:
                run_system = manifest[MANIFEST_PARAMS.RUN_SYSTEM.value]
                if len(run_system) > 0 and run_system != config['default']['name']:
                    logger.info('[{}] processing by {}.'.format(jid, run_system))
                    return
            if is_finished_job(manifest):
                logger.info('[{}] already finished.'.format(jid))
                return
            logger.info('[{}] process start.'.format(jid))
            if (is_exist_bucket_object(_bucket, os.path.join(jid, CANCEL_FILE)) and
                    manifest[MANIFEST_PARAMS.STATE.value] != JOB_STATE.COMPLETING.value):
                cancel_job(_bucket, jid, manifest)
            elif manifest[MANIFEST_PARAMS.STATE.value] == JOB_STATE.INIT.value:
                if not submit_job(_bucket, jid, manifest):
                    skip_stat_job = True

            if 'skip_stat_job' not in locals():
                stat_job(_bucket, jid, manifest)
            logger.info('[{}] process succeeded.'.format(jid))
        except Exception as e:
            logger.error('Error ({}): {}\n\n'.format(jid, e))
            logger.error(traceback.format_exc())
        upload_agent_log(config, _bucket)

    try:
        session = boto3.Session(profile_name=aws_profile)
        s3cli = session.client('s3', endpoint_url=endpoint_url)
        objs = s3cli.list_objects(Bucket=root_bucket, Delimiter='/')
        if not objs.get('CommonPrefixes'):
            logger.info('Jids is None.')
            return
        jids = [obj.get('Prefix')[:-1] for obj in objs.get('CommonPrefixes')]
        logger.info('jids = {}'.format(jids))
        futures = thread_pool.map(lambda jid: _process_job(jid), jids)
        for future in futures:
            pass
    except Exception as e:
        logger.error('Error: {}\n\n'.format(e))
        logger.error(traceback.format_exc())
    logger.debug('checknrun ended.')


def upload_agent_log(config: configparser.ConfigParser, bucket: object) -> None:
    '''It uploads a agent logs to cloud storage.

    Args:
        config (configparser.ConfigParser): CloudQ CLI configuration.
        bucket (S3.Bucket): A bucket where the job is stored.
    '''
    logfile = os.path.join(root_dir, LOG_FILE)
    s3file = os.path.join(AGENT_LOG_PREFIX, config['default']['name'])
    if os.path.isfile(logfile):
        bucket.upload_file(logfile, s3file)


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
                config[param['section']][param['key']] = str(param['default'])

    # check validity of cache directory path.
    global root_dir
    root_dir = os.path.expanduser(config['agent']['cloudq_directory'])
    global cache_dir
    cache_dir = os.path.join(root_dir, 'cache')
    try:
        os.makedirs(cache_dir, exist_ok=True)
    except Exception:
        raise Exception(MESSAGES.INVALID_CACHE_DIR_PATH.value.format(cache_dir))


def show_config(config: configparser.ConfigParser) -> None:
    '''It show configuration parameters.

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


def init_logger(args: argparse.Namespace, config: configparser.ConfigParser) -> None:
    '''It setups logger object.
    '''
    logfile = os.path.join(root_dir, LOG_FILE)
    if os.path.isfile(logfile):
        os.remove(logfile)

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(logging.Formatter(LOG_STDOUT_FORMAT))
    file_handler = logging.FileHandler(filename=logfile)
    file_handler.setFormatter(logging.Formatter(LOG_FILE_FORMAT))
    handlers = [file_handler, stdout_handler]
    logging.basicConfig(handlers=handlers)

    if args.log_level == 'INFO' or args.log_level == 'DEBUG':
        log_level = args.log_level
    else:
        log_level = config['default']['log_level']

    log_level = args.log_level
    if not args.log_level:
        log_level = logging.INFO

    global logger
    logger = logging.getLogger(PROCESS_NAME)
    logger.setLevel(log_level)


def create_default_config() -> str:
    '''It creates default configuration files in home directory.

    Returns:
        str: configration file path.
    '''
    data_dir = os.path.expanduser('~/.cloudq/agent')
    default_dir = os.path.join(os.path.dirname(__file__), 'data')
    config_path = os.path.join(data_dir, CONFIG_FILE)

    if not os.path.isdir(data_dir):
        shutil.copytree(default_dir, data_dir)

    if not os.path.isfile(config_path):
        config_path = os.path.join(default_dir, CONFIG_FILE)

    return config_path


def main() -> None:
    '''the entry point.
    '''
    try:
        config_path = create_default_config()
        if not os.path.isfile(config_path):
            raise Exception(MESSAGES.NO_CONFIG_FILE.value.format(CONFIG_FILE))

        parser = argparse.ArgumentParser(add_help=True)
        parser.add_argument('--daemon', action='store_true', help='run daemon mode')
        parser.add_argument('--log_level', help='specify log level. ')
        args = parser.parse_args()

        global config
        config = configparser.ConfigParser()
        config.read(config_path, encoding=CONFIG_FILE_ENCODING)

        _check_config(config)
        init_logger(args, config)
        logger.info('Agent start.')
        logger.info('=================== config ====================')
        show_config(config)
        logger.info('===============================================')

        global job_manager
        job_manager = JobManagerAccessor(config['agent']['type'])

        global meta_job_converter
        meta_job_converter = MetaJobScriptConverterAccessor(config['agent']['type'])
        meta_job_converter.set_unique_name(config['default']['name'])

        global thread_pool
        thread_pool = ThreadPoolExecutor(max_workers=int(config['agent']['num_procs']))

        if not args.daemon:
            checknrun()
            logger.info('Agent succeeded.')
            return

        # FIXME daemon mode
        run_interval = int(config['agent']['daemon_interval'])
        while True:
            checknrun()
            time.sleep(run_interval)
            logger.debug('')
    except Exception as e:
        if logger is not None:
            logger.error('Error: {}\n\n'.format(e))
            logger.debug(traceback.format_exc())
        else:
            print('Error: {}\n\n'.format(e), file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
        if 'parser' in locals():
            parser.print_help()


if __name__ == '__main__':
    main()
