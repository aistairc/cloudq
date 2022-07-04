# base: cloudq agent base
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
from abc import ABCMeta, abstractmethod


class AbstractJobManager(metaclass=ABCMeta):
    '''The job management interface
    '''

    @property
    @abstractmethod
    def SYSTEM_NAME(self) -> str:
        '''It returns system name
        '''
        pass

    @abstractmethod
    def submit_job(self, manifest: dict) -> dict:
        '''It submit a job.

        Args:
            manifest (dict): a job manifest.
        Returns:
            dict: a job manifest added local parameters.
        '''
        pass

    @abstractmethod
    def get_jobs_status(self) -> dict:
        '''It returns job status list.

        Returns:
            list: job status list.
        '''
        pass

    @abstractmethod
    def cancel_job(self, manifest: dict, force: bool) -> dict:
        '''It cancels a job.

        Args:
            manifest (dict): a job manifest.
            force (bool): If true, the job cancels forcibly.
        Returns:
            dict: a job manifest.
        '''
        pass

    @abstractmethod
    def get_job_log(self, manifest: dict, error: bool = False) -> dict:
        '''It saves a job log.

        Args:
            manifest (dict): a job manifest.
            error (bool): If true, returns error log.
        Returns:
            dict: a job manifest.
        '''
        pass


class AbstractMetaJobScriptConverter(metaclass=ABCMeta):
    '''The meta job script conversion interface
    '''

    @property
    @abstractmethod
    def SYSTEM_NAME(self) -> str:
        '''It returns system name
        '''
        pass

    @abstractmethod
    def set_unique_name(self, name: str) -> None:
        '''It stores unique system name

        Args:
            name (dict): a unique system name.
        '''
        pass

    @abstractmethod
    def to_local_job_script(self, manifest: dict, endpoint_url: str, aws_profile: str) -> dict:
        '''It converts meta job script to local job script

        Args:
            manifest (dict): a job manifest.
            endpoint_url (str): the endpoint URL of S3 bucket.
            aws_profile (str): the AWS profile.
        Returns:
            dict: a job manifest.
        '''
        pass
