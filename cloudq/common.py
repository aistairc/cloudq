# common: cloudq common library
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
import datetime
import json
import os
import tempfile
from enum import Enum

STAGEOUT_FILE = 'output.zip'
'''Name of an archive file that containts job outputs on an object storage.
'''

MANIFEST_FILE = 'manifest.json'
'''Name of a job manifest file on an object storage.
'''

PROJECT_DEF_FILE = 'project'
'''Name of a project definition file on an object storage.
'''

RESOURCE_DEF_FILE = 'resource'
'''Name of a project definition file on an object storage.
'''

STDOUT_FILE = 'stdout'
'''Name of job's standard outout file on an object storage.
'''

STDERR_FILE = 'stderr'
'''Name of job's standard error file on an object storage.
'''

CANCEL_FILE = 'cancel'
'''Name of cancel file on an object storage.
'''

AGENT_LOG_PREFIX = 'agent'
'''Name of agent log's prefix on an object storage.
'''

INITIAL_TIME = '-'
'''The string of initial datetime in manifest file.
'''


class JOB_STATE(Enum):
    '''Name of job's state.
    '''
    INIT = 'INIT'
    READY = 'READY'
    RUN = 'RUN'
    DELETING = 'DELETING'
    COMPLETING = 'COMPLETING'
    ERROR = 'ERROR'
    DONE = 'DONE'
    TIMEOUT = 'TIMEOUT'
    DELETED = 'DELETED'


class MANIFEST_PARAMS(Enum):
    '''Name of parameters in manifest.
    '''
    UUID = 'uuid'
    JOB_ID = 'jobid'
    NAME = 'name'
    SCRIPT_TYPE = 'jobscript_type'
    HOLD_JOB_ID = 'hold_jid'
    ARRAY_TASK_ID = 'array_tid'
    SUBMIT_TO = 'submit_to'
    SUBMIT_OPT = 'submit_opt'
    STATE = 'state'
    WORK_DIR = 'workdir'
    RUN_SYSTEM = 'run_system'
    LOCAL_ACCOUNT = 'local_account'
    LOCAL_GROUP = 'local_group'
    LOCAL_NAME = 'local_name'
    SUBMIT_COMMAND = 'submit_command'
    TIME_SUBMIT = 'time_submit'
    TIME_RECEIVE = 'time_receive'
    TIME_READY = 'time_ready'
    TIME_START = 'time_start'
    TIME_SO_START = 'time_stageout_start'
    TIME_SO_FINISH = 'time_stageout_finish'
    TIME_FINISH = 'time_finish'
    SIZE_INPUT = 'size_input'
    SIZE_OUTPUT = 'size_output'
    ERROR_MSG = 'error_msg'


class SCRIPT_TYPES(Enum):
    '''Name of job script types.
    '''
    LOCAL = 'local'
    META = 'meta'


def get_manifest(bucket: object, id_: str) -> dict:
    '''It gets a manifest of a job from an object storage.

    Args:
        bucket (S3.Bucket): A bucket where the job manifest is downloaded.
        id_ (str): Job ID.

    Returns:
        dict[str: obj]: A job manifest.
    '''
    with tempfile.TemporaryDirectory() as d:
        s3file = combine_s3_path(id_, MANIFEST_FILE)
        path = os.path.join(d, MANIFEST_FILE)
        try:
            bucket.download_file(s3file, path)
        except Exception:
            return None

        with open(path, mode='r') as f:
            manifest = json.load(f)
            return manifest


def put_manifest(bucket: object, id_: str, manifest: dict) -> None:
    '''It puts a manifest of a job to an object storage.

    Args:
        bucket (S3.Bucket): A bucket where the job manifest is downloaded.
        id_ (str): Job ID.
        manifest (dict[str: obj]): A job manifest.
    '''
    with tempfile.TemporaryDirectory() as d:
        s3file = combine_s3_path(id_, MANIFEST_FILE)
        path = os.path.join(d, MANIFEST_FILE)

        with open(path, mode='w') as f:
            json.dump(manifest, f, indent=4)
        bucket.upload_file(path, s3file)
        os.remove(path)


def is_exist_bucket_object(bucket: object, s3path: str) -> bool:
    '''It returns the object is exist or not on the bucket.

    Args:
        bucket (S3.Bucket): A bucket where the job manifest is downloaded.
        s3path (str): The object path on an object storage.

    Returns:
        bool: If the object is exist, returns true.
    '''
    objects = bucket.objects.filter(Prefix=s3path)
    if list(objects.limit(1)):
        return True
    else:
        return False


def is_finished_job(manifest: dict) -> bool:
    '''It returns the job is finished or not.

    Args:
        manifest (dict[str: obj]): A job manifest.

    Returns:
        bool: If the job is finished, returns true.
    '''
    finished = [JOB_STATE.DONE.value, JOB_STATE.ERROR.value,
                JOB_STATE.DELETED.value, JOB_STATE.TIMEOUT.value]
    if manifest[MANIFEST_PARAMS.STATE.value] in finished:
        return True
    else:
        return False


def current_time() -> str:
    '''It returns the current time in ISO format string.

    Returns:
        str: Current time.
    '''
    tz = datetime.timezone(datetime.timedelta(hours=0), 'UTC')
    return datetime.datetime.now(tz).isoformat(timespec='seconds')


def iso_to_datetime(iso_str) -> datetime.datetime:
    '''It returns a datetime object from a string of ISO formatted date.

    Args:
        iso_str (str): Date in ISO formatted

    Returns:
        datetime.datetime
    '''
    if iso_str and iso_str != INITIAL_TIME:
        try:
            dt = datetime.datetime.strptime(iso_str, '%Y-%m-%dT%H:%M:%S%z')
        except ValueError:
            dt = datetime.datetime.strptime(iso_str, '%Y-%m-%dT%H:%M:%S')
        return dt
    else:
        return datetime.datetime.utcfromtimestamp(0)


def time_iso_to_readable(iso_str: str) -> str:
    '''It returns a human readable date from a string of ISO formatted date.

    Args:
        iso_str (str): Date in ISO formatted

    Returns:
        str
    '''
    if iso_str:
        if iso_str == INITIAL_TIME:
            return iso_str
        else:
            dt = iso_to_datetime(iso_str)
            if dt.tzinfo:
                return dt.strftime('%Y/%m/%d %H:%M:%S %Z')
            else:
                return dt.strftime('%Y/%m/%d %H:%M:%S')
    else:
        return ''


def combine_s3_path(str_first: str, str_second: str) -> str:
    '''It returns a combine path for s3.

    Args:
        str_front (str): The first half of the string you want to combine.
        str_back (str): The second half of the string you want to combine.

    Returns:
        str: Combined string.
    '''
    return str_first + '/' + str_second
