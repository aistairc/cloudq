# setup: cloudq setup script
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
import ast
import re
import os
import setuptools

PACKAGE_NAME = 'cloudq'


def read_requirements(target=None):
    package_pattern = re.compile('^([^<=>]+)[<=>].*')
    if target is not None:
        reqs_path = f'requirements_{target}.txt'
    else:
        reqs_path = 'requirements.txt'
    requirements = []
    with open(reqs_path, 'r') as reqf:
        for line in reqf:
            found = package_pattern.search(line.strip())
            if found:
                requirements.append(found.group(1))
    return requirements


with open(os.path.join(PACKAGE_NAME, '__init__.py')) as f:
    match = re.search(r'__version__\s+=\s+(.*)', f.read())
VERSION = str(ast.literal_eval(match.group(1)))

with open('README.md') as f:
    LONG_DESCRIPTION = f.read()

setuptools.setup(
    # metadata
    name=PACKAGE_NAME,
    version=VERSION,
    license='Apache License, Version 2.0',
    author='Shinichiro Takizawa, AIST',
    author_email='shinichiro.takizawa@aist.go.jp',
    description='A cloud storage-based meta scheduler.',
    long_description=LONG_DESCRIPTION,
    long_description_content_type='text/markdown',
    url='https://github.com/aistairc/cloudq',
    classifiers=[
        'Programming Language :: Python :: 3.6',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
    ],
    # options
    packages=setuptools.find_packages(),
    include_package_data=True,
    package_data={
        PACKAGE_NAME: ['data/*', 'example/*', 'aws/*', 'aws/data/*', 'aws/data/default/*',
                       'aws/example/enable-docker/*', 'aws/example/enable-gpu/*'],
    },
    zip_safe=False,
    platforms='any',
    python_requires='>=3.8',
    install_requires=read_requirements(),
    extras_require={
        'abci': read_requirements('abci'),
        'aws': read_requirements('aws'),
    },
    entry_points={
        'console_scripts': [
            'cloudqcli = {}.client:main'.format(PACKAGE_NAME),
            'cloudqd = {}.agent:main'.format(PACKAGE_NAME),
            'cloudqaws = {}.aws.cloudqaws:main'.format(PACKAGE_NAME),
        ],
    },
)
