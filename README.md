# Cloudq

Cloud storage-based meta scheduler

Copyright 2021 National Institute of Advanced Industrial Science and Technology (AIST), Japan and
Hitachi, Ltd.

This program is licensed under the Apache License, Version2.0.


## Overview

Cloudq is a meta scheduler that submits jobs to and manages them on clouds or supercomputers in which compute nodes are managed by job schedulers.
It has the following features.

- Input, output and status of jobs are stored on an Amazon S3 compatible object storage.
- User can write a jobscript in two formats; **local jobscript** and **meta jobscript**.
  A job described in meta jobscript can run on any cloud or supercomputer managed under Cloudq.
  A job described in local jobscript runs only on a specific system, but the job can use all functions the system provides.
- The installation of Cloudq does not require administrator privileges.

Cloudq consists of two components.

One is **Agent** which submits jobs to and manages them on a system.
If you have accounts on multiple clouds or supercomputers, you can submit jobs to them using Cloudq by installing Agents on them.

Currently, Cloudq Agent supports the following systems.

- [ABCI](https://abci.ai//)

The other Cloudq component is **Client**.
By using Client on a user's terminal, user can submit and manage jobs on Cloudq.


## Requirements

Cloudq Client
- OS: Linux, MacOS and Windows
- Python: 3.6 or newer (Tested on Python 3.8.7)
- AWS CLI: 2.0 or newer (Tested on AWS CLI 2.1.30)

Cloudq Agent
- OS: Linux compatible OS (Tested on CentOS 7.5)
- Python: 3.6 or newer (Tested on Python 3.8.7)
- AWS CLI: 2.0 or newer (Tested on AWS CLI 2.1.30)


## Installation

### Cloudq Client

Cloudq Client need to be installed on computers where you submit jobs.

```console
$ aws configure
$ aws --endpoint-url https://s3.abci.ai s3 mb s3://cloudq

$ git clone git@github.com:aistairc/cloudq.git
$ cd cloudq
$ vi cloudq/data/config.ini
    <set system name and cloud storage configuration>
$ vi cloudq/data/project.ini
    <set your project name (*)>
$ vi cloudq/data/resource.ini
    <set resource types that you want to use (*)>

$ pip3 install -r requirements.txt
$ pip3 install .
```

(*) Setup is required when you use meta jobscript.

### Cloudq Agent

A Cloudq Agent need to be installed on a server on which the Agent can submit jobs to the job scheduler of the target system.

```console
$ aws configure
$ aws --endpoint-url https://s3.abci.ai s3 mb s3://cloudq

$ git clone git@github.com:aistairc/cloudq.git
$ cd cloudq
$ vi cloudq/data/config.ini
    <set system name and cloud storage configuration>

$ pip3 install -r requirements.txt
$ pip3 install .
```

### Change Configuration after Installation

To change the configuration after installation, you need to edit configuration files under
Python package directory.
The configuration files are stored in `(Python package directory)/cloudq/data/`.

The path of the Python package directory can be found with the following command.

```console
$ pip3 show cloudq
```

You can open to edit `cloudq/data/config.ini` by the following command.

```console
$ vi `pip3 show cloudq | grep Location | cut -d ' ' -f 2`/cloudq/data/config.ini
```


## Usage

### Agent Side (On Machines where Cloudq Agent Runs)

```console
$ cloudqd --daemon
```

### Client Side

#### Submit a Job
The following example submits a job described in local jobscript.

```console
$ cloudqcli submit --script cloudq/example/ljob_tf_mnist.abci.sh \
                   --submit_to YOUR_SYSTEM --submit_opt 'SUBMIT_OPTION'
Job (3f7e7681) ljob_tf_mnist.abci.sh has been submitted.
```

The following example submits a job described in meta jobscript.

```console
$ cloudqcli submit --script cloudq/example/mjob_tf_mnist.sh
Job (e210c27c) mjob_tf_mnist.sh has been submitted.
```

#### Submit a Dependent Job
The following example submits a job that depends on other jobs.

```console
$ cloudqcli submit --script cloudq/example/ljob_tf_mnist.abci.sh \
                   --submit_to YOUR_SYSTEM --submit_opt 'SUBMIT_OPTION' \
                   --hold_jid '3f7e7681,e210c27c'
Job (fc2d6f45) ljob_tf_mnist.abci.sh has been submitted.
```

#### Submit an Array Job
The following example submits an array job.

```console
$ cloudqcli submit --script cloudq/example/mjob_array.sh --array_tid 1-4:1
Job (a38c9a9f) mjob_array.sh has been submitted.
```

In the meta jobscript, the environment variables can be used to refer to task ID and other information.
See [Environment variables](#environment-variables)

#### Check the Status of a Job

```console
$ cloudqcli stat --id e210c27c
uuid                  e210c27c
jobid                 5150599
name                  mjob_tf_mnist.sh
jobscript_type        meta
hold_jid
array_tid
submit_to
submit_opt
state                 DONE
workdir               YOUR_HOME/.cloudq/cache/e210c27c
run_system            abci
local_account         YOUR_ACCOUNT
local_group           YOUR_GROUP
submit_command        qsub -g YOUR_GROUP mjob_tf_mnist.sh
time_submit           2021/01/13 09:55:34
time_receive          2021/01/13 10:05:47
time_ready            2021/01/13 10:05:47
time_start            2021/01/13 10:06:16
time_stageout_start   2021/01/13 10:06:33
time_stageout_finish  2021/01/13 10:06:33
time_finish           2021/01/13 10:06:33
size_input            516
size_output           1329
error_msg
submit_opt_local      -g YOUR_GROUP
local_name            mjob_tf_mnist_local.sh
```

#### Cancel a Job

```console
$ cloudqcli cancel --id e210c27c
Job (e210c27c) is canceled.
```

#### Display Log Messages
The following example display stdout messages of a job.

```console
$ cloudqcli log --id 3f7e7681
    <display stdout of the job>
```

The following example display stderr messages of a job.

```console
$ cloudqcli log --id 3f7e7681 --error
    <display stdout of the job>
```

The following example display log messages of an Cloudq Agent.

```console
$ cloudqcli log --agent YOUR_SYSTEM
    <display agent log>
```

#### Stageout (Get Job Input/Output/Log Files)

```console
$ cloudqcli stageout --id 3f7e7681
    <download job files in the current directory>
```

#### Delete Jobs or Agent logs
The following example deletes a completed job.

```console
$ cloudqcli delete --id 3f7e7681
Job (3f7e7681) is deleted.
```

The following example delete all completed jobs.

```console
$ cloudqcli delete --all
Job (3f7e7681) is deleted.
Job (e210c27c) is deleted.
```

The following example deletes a agent log.

```console
$ cloudqcli delete --agent YOUR_SYSTEM
Agent log (YOUR_SYSTEM) is deleted.
```

#### List Submitted/Running Jobs

```console
$ cloudqcli list
      job-ID                  name     state  run-system            submit at
-----------------------------------------------------------------------------
    3f7e7681  ljob_tf_mnist.abci.s      RUN         abci  2021/01/13 09:51:22
    e210c27c      mjob_tf_mnist.sh      READY       abci  2021/01/13 09:55:34
    fc2d6f45  ljob_tf_mnist.abci.s      INIT              2021/01/13 10:02:50
```

#### List Completed Jobs

```console
$ cloudqcli history
      job-ID                  name     state  run-system            submit at             start at            finish at
-----------------------------------------------------------------------------------------------------------------------
    3f7e7681  ljob_tf_mnist.abci.s      ERROR       abci  2021/01/13 09:51:22
    e210c27c      mjob_tf_mnist.sh      DONE        abci  2021/01/13 09:55:34  2021/01/13 10:06:16  2021/01/13 10:06:33
```

## Meta Jobscript

Meta jobscript is introduced to write a jobscript that runs on any systems Cloudq supports.
A jobscript written in Meta jobscript is converted to a local jobscript by a Cloudq agent when it receives a job.
Meta jobscript can use the following directives, functions and environment variables.

### Directives

|  Name  |  Explanation  |
| ---- | ---- |
|  run_on  |  [Optional] Name of a system that runs the job. If not specified, the job will be executed on the earliest scheduled system.  |
|  project  |  [Mandatory] Name of a research project.  It can be used for charge on some systems.  |
|  resource  |  [Mandatory] Name of resource type used to run the job.  |
|  n_resource  |  [Mandatory] Number of resources used to run the job.  |
|  walltime  |  [Optional] Walltime requested.  If not specified, the default walltime on the system is applied.  |
|  other_opts  |  [Optional] Options to the job submission command appended when the job is submitted.  |
|  container_img  |  [Optional] URL of container image used in the job.  It can be specified multiple times.  |

### Functions

#### Launch Container

```shell
cq_container_run IMG [CMD]
```

It launchs a container using the specified image.
The container runtime the system supports is used.

Arguments
- IMG:	Path of a container image.
- CMD:	A command and its options executed in the container.

#### Copy Cloud Storage Object

```shell
abci_cs_cp SRC DST [ENDPOINT [PROFILE]]
```

It copies files and objects between cloud storage and local filesystem.

Arguments
- SRC:	URL of source files/objects.
- DST:	URL of destination files/objects.
- ENDPOINT:	 URL of cloud storage endpoint.  It not specified, the endpoint URL specified in configuration file is used.
- PROFILE:	Name of AWS profile. If not specified, the AWS profile specified in configuration file is used.

### Environment Variables

|  Name  |  Explanation  |
| ---- | ---- |
|  SYSTEM  |  Name of a system that runs the job.  |
|  CONTAINER_IMG#  |  File name of a container image.  # will be replaced by a serial number starting with 0.  |
|  ARY_TASK_ID  |  Task ID of an array job.  |
|  ARY_TASK_FIRST  |  Task ID of the first task of an array job.  |
|  ARY_TASK_LAST  |  Task ID of the last task of an array job.  |
|  ARY_TASK_STEPSIZE  |  Step size of IDs of an array job.  |

### Example

Example meta jobscripts can be found in `cloudq/example` directory.

- mjob_array.sh
  - Array job example
- mjob_pt_mnist.sh
  - Download container image from NGC and then train MNIST using PyTorch on a singularity container
- mjob_tf_mnist.sh
  - Download container image from NGC and then train MNIST using TensorFlow on a singularity container
