# interface: cloudq agent interface
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
from abc import ABCMeta, abstractmethod
from enum import Enum


class MESSAGES(Enum):
    ''' List of console messages.
    '''
    UNSUPPORTED_SYSTEM_NAME = 'The system name is not supported: {}'


class AbstractJobManager(metaclass=ABCMeta):
    @property
    @abstractmethod
    def SYSTEM_NAME(self):
        pass

    @abstractmethod
    def submit_job(self, manifest):
        pass

    @abstractmethod
    def get_jobs_status(self):
        pass

    @abstractmethod
    def cancel_job(self, manifest, force=False):
        pass

    @abstractmethod
    def get_job_log(self, manifest, error=False):
        pass


class AbstractMetaJobScriptConverter(metaclass=ABCMeta):
    @property
    @abstractmethod
    def SYSTEM_NAME(self):
        pass

    @abstractmethod
    def to_local_job_script(self, manifest, endpoint_url, aws_profile):
        pass


# FIXME following two import comes here because of avoiding circular import. need to fix it.
# Import of job manager interfaces
from .abci import ABCIJobManager
# Import of meta job script converter interfaces
from .abci import ABCIMetaJobScriptConverter

JOB_MANAGER_IMPL_LIST = [
    ABCIJobManager
]

META_JOB_SCRIPT_CONVERTER_IMPL_LIST = [
    ABCIMetaJobScriptConverter
]


class JobManagerAccessor(AbstractJobManager):
    @property
    def SYSTEM_NAME(self):
        return ''

    def __init__(self, system):
        self.target = None
        for name in JOB_MANAGER_IMPL_LIST:
            obj = name()
            if (system == obj.SYSTEM_NAME):
                self.target = obj
                break

        if not self.target:
            raise ValueError(MESSAGES.UNSUPPORTED_SYSTEM_NAME.value.format(system))

    def submit_job(self, manifest):
        return self.target.submit_job(manifest)

    def get_jobs_status(self):
        return self.target.get_jobs_status()

    def cancel_job(self, manifest, force=False):
        return self.target.cancel_job(manifest, force)

    def get_job_log(self, manifest, error=False):
        return self.target.get_job_log(manifest, error)


class MetaJobScriptConverterAccessor(AbstractMetaJobScriptConverter):
    @property
    def SYSTEM_NAME(self):
        return ''

    def __init__(self, system):
        self.target = None
        for name in META_JOB_SCRIPT_CONVERTER_IMPL_LIST:
            obj = name()
            if (system == obj.SYSTEM_NAME):
                self.target = obj
                break

        if not self.target:
            raise ValueError(MESSAGES.UNSUPPORTED_SYSTEM_NAME.value.format(system))

    def to_local_job_script(self, manifest, endpoint_url, aws_profile):
        return self.target.to_local_job_script(manifest, endpoint_url, aws_profile)
