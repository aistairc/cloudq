# interface: cloudq agent interface
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
from enum import Enum
from .base import AbstractJobManager, AbstractMetaJobScriptConverter
# Import of job manager interfaces
from .abci import ABCIJobManager
from .slurm import SlurmJobManager
# Import of meta job script converter interfaces
from .abci import ABCIMetaJobScriptConverter
from .slurm import SlurmMetaJobScriptConverter


class MESSAGES(Enum):
    ''' List of console messages.
    '''
    UNSUPPORTED_SYSTEM_NAME = 'The system name is not supported: {}'


JOB_MANAGER_IMPL_LIST = [
    ABCIJobManager,
    SlurmJobManager
]

META_JOB_SCRIPT_CONVERTER_IMPL_LIST = [
    ABCIMetaJobScriptConverter,
    SlurmMetaJobScriptConverter
]


class JobManagerAccessor(AbstractJobManager):
    '''The accessor of job management interface
    '''

    @property
    def SYSTEM_NAME(self) -> str:
        '''It returns system name
        '''
        return ''

    def __init__(self, system: str) -> None:
        '''Constructor

        Args:
            system (str) : the system name
        '''
        self.target = None
        for name in JOB_MANAGER_IMPL_LIST:
            obj = name()
            if (system == obj.SYSTEM_NAME):
                self.target = obj
                break

        if not self.target:
            raise ValueError(MESSAGES.UNSUPPORTED_SYSTEM_NAME.value.format(system))

    def submit_job(self, manifest: dict) -> dict:
        '''It submit a job.

        Args:
            manifest (dict): a job manifest.
        Returns:
            dict: a job manifest added local parameters.
        '''
        return self.target.submit_job(manifest)

    def get_jobs_status(self) -> dict:
        '''It returns job status list.

        Returns:
            list: job status list.
        '''
        return self.target.get_jobs_status()

    def cancel_job(self, manifest: dict, force: bool) -> dict:
        '''It cancels a job.

        Args:
            manifest (dict): a job manifest.
            force (bool): If true, the job cancels forcibly.
        Returns:
            dict: a job manifest.
        '''
        return self.target.cancel_job(manifest, force)

    def get_job_log(self, manifest: dict, error: bool = False) -> dict:
        '''It saves a job log.

        Args:
            manifest (dict): a job manifest.
            error (bool): If true, returns error log.
        Returns:
            dict: a job manifest.
        '''
        return self.target.get_job_log(manifest, error)


class MetaJobScriptConverterAccessor(AbstractMetaJobScriptConverter):
    '''The accessor of meta job script conversion interface
    '''

    @property
    def SYSTEM_NAME(self) -> str:
        '''It returns system name
        '''
        return ''

    def __init__(self, system: str) -> None:
        '''Constructor

        Args:
            system (str) : the system name
        '''
        self.target = None
        for name in META_JOB_SCRIPT_CONVERTER_IMPL_LIST:
            obj = name()
            if (system == obj.SYSTEM_NAME):
                self.target = obj
                break

        if not self.target:
            raise ValueError(MESSAGES.UNSUPPORTED_SYSTEM_NAME.value.format(system))

    def set_unique_name(self, name: str) -> None:
        '''It stores unique system name

        Args:
            name (dict): a unique system name.
        '''
        self.target.set_unique_name(name)

    def to_local_job_script(self, manifest: dict, endpoint_url: str, aws_profile: str) -> dict:
        '''It converts meta job script to local job script

        Args:
            manifest (dict): a job manifest.
            endpoint_url (str): the endpoint URL of S3 bucket.
            aws_profile (str): the AWS profile.
        Returns:
            dict: a job manifest.
        '''
        return self.target.to_local_job_script(manifest, endpoint_url, aws_profile)
