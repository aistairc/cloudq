# abci: cloudq agent for ABCI
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
import configparser
import glob
import logging
import os
import re
import shutil
import subprocess
from enum import Enum

from .interface import AbstractJobManager
from .interface import AbstractMetaJobScriptConverter
from .common import STDOUT_FILE, STDERR_FILE, PROJECT_DEF_FILE, RESOURCE_DEF_FILE
from .common import MANIFEST_PARAMS, JOB_STATE

logger = logging.getLogger('CloudQ Agent').getChild('abci')

PROCESS_NAME = 'CloudQ Agent'
'''Name of this process.
'''

SYSTEM_NAME = 'abci'

PATTERN_SUBMIT_ABCI_JOB_ID_EXTRACT = r'^Your job (\d+) \(".*"\) has been submitted'
'''Regular expression pattern for extracting job ID from submit command on ABCI. (normal job)
'''

PATTERN_SUBMIT_ABCI_ARRAY_JOB_ID_EXTRACT = r'^Your job-array (\d+).\S+ \(".*"\) has been submitted'
'''Regular expression pattern for extracting job ID from submit command on ABCI. (array job)
'''

PATTERN_STAT_ABCI = r'^\s*(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)'
'''Regular expression pattern for extracting job info from stat command on ABCI.
'''

PATTERN_STDOUT_FILE = r'\S+\.o\S+$'
'''Regular expression pattern of stdout files on ABCI.
'''

PATTERN_STDERR_FILE = r'\S+\.e\S+$'
'''Regular expression pattern of stderr files on ABCI.
'''

PATTERN_ARRAYJOB_LOG_FILE = r'^\S+\.\S+\.(\S+)$'
'''Regular expression pattern of stdout/stderr files for array job.
'''

PATTERN_META_JS_INSTRUCTIONS = r'#\$\s*(\S+)\s*:\s*([\s\S]+)\s*'
'''Regular expression pattern for meta job script's instructions.
'''

ENV_VARS_AND_FUNCS = '\
export ARY_TASK_ID=$SGE_TASK_ID\n\
export ARY_TASK_FIRST=$SGE_TASK_FIRST\n\
export ARY_TASK_LAST=$SGE_TASK_LAST\n\
export ARY_TASK_STEPSIZE=$SGE_TASK_STEPSIZE\n\
export TMPDIR=$SGE_LOCALDIR\n\
\n\
source /etc/profile.d/modules.sh\n\
module load singularitypro/3.7\n\
module load aws-cli/2.1\n\
\n\
cq_container_run() {{\n\
    singularity exec --nv $@\n\
}}\n\
abci_cs_cp() {{\n\
    SRC=$1\n\
    DST=$2\n\
    if [ $# -gt 3 ]; then\n\
        ENDPOINT=$3\n\
    else\n\
        ENDPOINT={}\n\
    fi\n\
    if [ $# -gt 4 ]; then\n\
        PROFILE=$4\n\
    else\n\
        PROFILE={}\n\
    fi\n\
    aws --endpoint-url $ENDPOINT --profile $PROFILE s3 cp s3://$SRC s3://$DST\n\
}}\n\n'
'''List of environment variables.
'''


class LOCAL_MANIFEST_PARAMS(Enum):
    LOCAL_SUBMIT_OPT = 'submit_opt_local'


class META_JS_INSTRUCTION_KEYS(Enum):
    RUN_ON = 'run_on'
    PROJECT = 'project'
    RESOURCE = 'resource'
    N_RESOURCE = 'n_resource'
    WALLTIME = 'walltime'
    OTHER_OPTS = 'other_opts'
    CONTAINER_IMG = 'container_img'


class MESSAGES(Enum):
    ''' List of console messages.
    '''
    SCRIPT_FILE_NOT_FOUND = 'The script file is not found:{}'
    IRREGAL_PROJECT_NAME = 'Irregal abstract project name: {}'
    IRREGAL_RESOURCE_NAME = 'Irregal abstract resource name: {}'
    NO_MANDATORY_INSTRUCTION = 'The instruction is not specified: {}'


class ABCIJobManager(AbstractJobManager):
    @property
    def SYSTEM_NAME(self):
        return SYSTEM_NAME

    def submit_job(self, manifest):
        logger.debug('submit_job start. UUID={}'.format(manifest[MANIFEST_PARAMS.UUID.value]))
        if MANIFEST_PARAMS.LOCAL_NAME.value in manifest:
            name = manifest[MANIFEST_PARAMS.LOCAL_NAME.value]
        else:
            name = manifest[MANIFEST_PARAMS.NAME.value]
        submit_cmd = ['qsub', name]

        if LOCAL_MANIFEST_PARAMS.LOCAL_SUBMIT_OPT.value in manifest:
            if len(manifest[LOCAL_MANIFEST_PARAMS.LOCAL_SUBMIT_OPT.value]) > 0:
                submit_cmd[1:1] = manifest[LOCAL_MANIFEST_PARAMS.LOCAL_SUBMIT_OPT.value].split()
        if MANIFEST_PARAMS.ARRAY_TASK_ID.value in manifest:
            if len(manifest[MANIFEST_PARAMS.ARRAY_TASK_ID.value]) > 0:
                submit_cmd[1:1] = ['-t', manifest[MANIFEST_PARAMS.ARRAY_TASK_ID.value]]
        submit_cmd[1:1] = manifest[MANIFEST_PARAMS.SUBMIT_OPT.value].split()
        submit_cmd[1:1] = ['-cwd']

        # Store submit command to manifest.
        manifest[MANIFEST_PARAMS.SUBMIT_COMMAND.value] = ' '.join(submit_cmd)

        # Store local group name to manifest.
        if '-g' in submit_cmd:
            group_index = submit_cmd.index('-g') + 1
            if group_index < len(submit_cmd):
                manifest[MANIFEST_PARAMS.LOCAL_GROUP.value] = submit_cmd[group_index]

        logger.debug('Run submit command: {}'.format(' '.join(submit_cmd)))
        proc = subprocess.Popen(submit_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (out, err) = proc.communicate()
        result = re.match(PATTERN_SUBMIT_ABCI_JOB_ID_EXTRACT, out.decode())
        if not result:
            result = re.match(PATTERN_SUBMIT_ABCI_ARRAY_JOB_ID_EXTRACT, out.decode())

        if result:
            logger.info(out.decode())
            manifest[MANIFEST_PARAMS.JOB_ID.value] = result.group(1)
        else:
            logger.info(err.decode())
            manifest[MANIFEST_PARAMS.ERROR_MSG.value] = err.decode()
        logger.debug('submit_job ended. UUID={} JobID={}'.format(manifest[MANIFEST_PARAMS.UUID.value],
                                                                 manifest[MANIFEST_PARAMS.JOB_ID.value]))
        return manifest

    def get_jobs_status(self):
        logger.debug('get_jobs_status start.')
        jobs = []
        cmd = ['qstat']
        logger.debug('Run submit command: {}'.format(' '.join(cmd)))
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (out, err) = proc.communicate()
        out = out.decode().splitlines()
        if out == []:
            logger.debug('get_jobs_status ended. {} jobs'.format(len(jobs)))
            return jobs

        for line in out:
            result = re.match(PATTERN_STAT_ABCI, line)
            if not result:
                continue

            jobid = result.group(1)
            qst = result.group(5)
            if qst == 'r':
                state = JOB_STATE.RUN.value
            elif qst == 'qw':
                state = JOB_STATE.READY.value
            elif qst == 'E':
                state = JOB_STATE.ERROR.value
            elif qst == 'd':
                state = JOB_STATE.DELETING.value
            else:
                state = ''
            logger.debug('  jobid:{}, state:{}'.format(jobid, state))
            jobs.append((jobid, state))
        logger.debug('get_jobs_status ended. {} jobs'.format(len(jobs)))
        return jobs

    def cancel_job(self, manifest, force):
        logger.debug('cancel_job start. UUID={} JobID={}'.format(manifest[MANIFEST_PARAMS.UUID.value],
                                                                 manifest[MANIFEST_PARAMS.JOB_ID.value]))
        if force:
            cancel_cmd = ['qdel', '-f', manifest[MANIFEST_PARAMS.JOB_ID.value]]
        else:
            cancel_cmd = ['qdel', manifest[MANIFEST_PARAMS.JOB_ID.value]]

        logger.debug('Run cancel command: {}'.format(' '.join(cancel_cmd)))
        proc = subprocess.Popen(cancel_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (out, err) = proc.communicate()
        logger.info(out.decode())
        logger.debug('cancel_job ended. UUID={} JobID={}'.format(manifest[MANIFEST_PARAMS.UUID.value],
                                                                 manifest[MANIFEST_PARAMS.JOB_ID.value]))
        return manifest

    def get_job_log(self, manifest, error):
        logger.debug('get_job_log start. UUID={}, error={}'.format(manifest[MANIFEST_PARAMS.UUID.value], error))
        workdir = manifest[MANIFEST_PARAMS.WORK_DIR.value]
        if error:
            reg = PATTERN_STDERR_FILE
            filename = STDERR_FILE
        else:
            reg = PATTERN_STDOUT_FILE
            filename = STDOUT_FILE

        src_list = [p for p in glob.glob(os.path.join(workdir, '*')) if re.match(reg, p)]
        if len(src_list) == 1:
            dst = os.path.join(workdir, filename)
            shutil.copyfile(src_list[0], dst)
            logger.debug('The log file is created/updated: {}'.format(dst))
        elif len(src_list) > 1:
            for src in src_list:
                result = re.match(PATTERN_ARRAYJOB_LOG_FILE, os.path.basename(src))
                if result:
                    tid = result.group(1)
                    dst = os.path.join(workdir, '{}.{}'.format(filename, tid))
                    shutil.copyfile(src, dst)
                    logger.debug('The log file is created/updated: {}'.format(dst))
                else:
                    logger.debug('Unexpected format. Failed to get task ID. UUID:{}, file:{}'.format(manifest[MANIFEST_PARAMS.UUID.value], src))

        logger.debug('get_job_log ended. UUID={}, error={}'.format(manifest[MANIFEST_PARAMS.UUID.value], error))
        return manifest


class ABCIMetaJobScriptConverter(AbstractMetaJobScriptConverter):
    @property
    def SYSTEM_NAME(self):
        return SYSTEM_NAME

    def to_local_job_script(self, manifest, endpoint_url, aws_profile):
        logger.debug('to_local_job_script start. UUID={}'.format(manifest[MANIFEST_PARAMS.UUID.value]))

        org_script_name = manifest[MANIFEST_PARAMS.NAME.value]
        if not os.path.isfile(org_script_name):
            manifest[MANIFEST_PARAMS.ERROR_MSG.value] = MESSAGES.SCRIPT_FILE_NOT_FOUND.value.format(org_script_name)
            return manifest
        with open(org_script_name, 'r') as f:
            org_script = f.read().splitlines()

        linenum = 0
        instructions = {}
        for line in org_script:
            linenum += 1
            if len(line.strip()) == 0:
                continue

            result = re.match(PATTERN_META_JS_INSTRUCTIONS, line)
            if result:
                if result.group(1) == META_JS_INSTRUCTION_KEYS.CONTAINER_IMG.value:
                    if META_JS_INSTRUCTION_KEYS.CONTAINER_IMG.value in instructions:
                        instructions[result.group(1)].append(result.group(2))
                    else:
                        instructions[result.group(1)] = [result.group(2)]
                else:
                    instructions[result.group(1)] = result.group(2)
            elif line.startswith('#!'):
                continue
            elif not line.startswith('#$'):
                first_script_line = linenum
                break

        if META_JS_INSTRUCTION_KEYS.PROJECT.value in instructions:
            prj_name = instructions[META_JS_INSTRUCTION_KEYS.PROJECT.value]
            prj_def = configparser.ConfigParser()
            prj_def.read(PROJECT_DEF_FILE, encoding='utf-8')
            if prj_name not in prj_def.sections():
                raise Exception(MESSAGES.IRREGAL_PROJECT_NAME.value.format(prj_name))
            try:
                prj_name = prj_def[prj_name][manifest[MANIFEST_PARAMS.RUN_SYSTEM.value]]
                manifest[LOCAL_MANIFEST_PARAMS.LOCAL_SUBMIT_OPT.value] = '-g {}'.format(prj_name)
            except configparser.NoOptionError:
                raise Exception(MESSAGES.IRREGAL_PROJECT_NAME.value.format(prj_name))
        else:
            raise Exception(MESSAGES.NO_MANDATORY_INSTRUCTION.value.format(META_JS_INSTRUCTION_KEYS.PROJECT.value))

        new_script = []

        # Add instructions.
        if org_script[0].startswith('#!'):
            new_script.append(org_script[0])
        if META_JS_INSTRUCTION_KEYS.RESOURCE.value in instructions:
            if META_JS_INSTRUCTION_KEYS.N_RESOURCE.value in instructions:
                res_name = instructions[META_JS_INSTRUCTION_KEYS.RESOURCE.value]
                res_num = instructions[META_JS_INSTRUCTION_KEYS.N_RESOURCE.value]
                res_def = configparser.ConfigParser()
                res_def.read(RESOURCE_DEF_FILE, encoding='utf-8')
                if res_name not in res_def.sections():
                    raise Exception(MESSAGES.IRREGAL_RESOURCE_NAME.value.format(res_name))
                try:
                    res_type = res_def[res_name][manifest[MANIFEST_PARAMS.RUN_SYSTEM.value]]
                    new_script.append('#$ -l {}={}'.format(res_type, res_num))
                except configparser.NoOptionError:
                    raise Exception(MESSAGES.IRREGAL_RESOURCE_NAME.value.format(res_name))
            else:
                raise Exception(MESSAGES.NO_MANDATORY_INSTRUCTION.value.format(META_JS_INSTRUCTION_KEYS.N_RESOURCE.value))
        else:
            raise Exception(MESSAGES.NO_MANDATORY_INSTRUCTION.value.format(META_JS_INSTRUCTION_KEYS.RESOURCE.value))
        if META_JS_INSTRUCTION_KEYS.WALLTIME.value in instructions:
            new_script.append('#$ -l h_rt={}'.format(instructions[META_JS_INSTRUCTION_KEYS.WALLTIME.value]))
        if META_JS_INSTRUCTION_KEYS.OTHER_OPTS.value in instructions:
            opts = instructions[META_JS_INSTRUCTION_KEYS.OTHER_OPTS.value]
            key = ''
            for opt in opts.split(' '):
                if len(key) == 0 and opt.startswith('-'):
                    key = opt
                    continue

                if len(key) > 0:
                    new_script.append('#$ {} {}'.format(key, opt))
                    key = ''
                else:
                    new_script.append('#$ {}'.format(opt))
        new_script.append('')

        # Add environment variables and functions.
        if META_JS_INSTRUCTION_KEYS.RUN_ON.value in instructions:
            system_name = instructions[META_JS_INSTRUCTION_KEYS.RUN_ON.value]
        else:
            system_name = SYSTEM_NAME
        new_script.append('export SYSTEM={}'.format(system_name))

        vars_and_funcs = ENV_VARS_AND_FUNCS.format(endpoint_url, aws_profile).splitlines()
        new_script.extend(vars_and_funcs)

        # Add scripts.
        if META_JS_INSTRUCTION_KEYS.CONTAINER_IMG.value in instructions:
            for index in range(len(instructions[META_JS_INSTRUCTION_KEYS.CONTAINER_IMG.value])):
                url = instructions[META_JS_INSTRUCTION_KEYS.CONTAINER_IMG.value][index]
                new_script.append('export CONTAINER_IMG{}={}'.format(index, url))
                # new_script.append('CONTAINER_IMG{}_URL={}'.format(index, url))
                # new_script.append('export CONTAINER_IMG{}={}'.format(index, os.path.basename(url)))
                # new_script.append('singularity pull $CONTAINER_IMG{} $CONTAINER_IMG{}_URL'.format(index, index))
                # new_script.append('unset CONTAINER_IMG{}_URL'.format(index))
                new_script.append('')

        if first_script_line:
            new_script.extend(org_script[first_script_line-1:])

        # if META_JS_INSTRUCTION_KEYS.CONTAINER_IMG.value in instructions:
        #     for index in range(len(instructions[META_JS_INSTRUCTION_KEYS.CONTAINER_IMG.value])):
        #         new_script.append('rm $CONTAINER_IMG{}'.format(index))

        root, ext = os.path.splitext(org_script_name)
        manifest[MANIFEST_PARAMS.LOCAL_NAME.value] = '{}_local{}'.format(root, ext)
        with open(manifest[MANIFEST_PARAMS.LOCAL_NAME.value], mode='w') as fp:
            fp.write('\n'.join(new_script))

        logger.debug('to_local_job_script ended. UUID={}'.format(manifest[MANIFEST_PARAMS.UUID.value]))
        return manifest
