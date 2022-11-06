# CloudQ

Cloud storage-based meta scheduler

Copyright 2022 National Institute of Advanced Industrial Science and Technology (AIST), Japan and
Hitachi, Ltd.

This program is licensed under the Apache License, Version2.0.


## Overview

CloudQ is a job management system that targets on executing AI/HPC tasks on on-premise systems, cloud and supercomputers with a unified interface.
It has the following features.

- Input, output and status of jobs are stored on an Amazon S3 compatible object storage.
- User can write a jobscript in two formats; **local jobscript** and **meta jobscript**.
  A job described in meta jobscript can run on any systems managed under CloudQ.
  A job described in local jobscript runs only on a specific system, but the job can use all functions the system provides.
- The installation and administration of CloudQ do not require administrator privileges.

CloudQ consists of two components.

One is **Agent** which submits jobs and manages them on a system.
If you have accounts on multiple clouds or supercomputers, you can submit jobs to them using CloudQ by installing Agents on them.

Currently, CloudQ Agent supports the following systems.

- [ABCI](https://abci.ai/)
- [Amazon Web Services (AWS)](https://aws.amazon.com/)

The second CloudQ component is **Client**.
By using Client on a user's terminal, user can submit and manage jobs on CloudQ.

![CloudQ Architecture](/docs/fig_cloudq_arch.png)

CloudQ provides an additional component named **Builder**.
Builder helps setting up compute clusters on clouds.

Currently, CloudQ Builder for AWS is available.
CloudQ Builder for AWS creates clusters using Slurm as their job scheduler.
It installs CloudQ Agent on cluster's head node.

## Requirements

CloudQ Client
- OS: Linux, MacOS and Windows
- Python: 3.8 or newer (Tested on Python 3.8.7)
- AWS CLI: 2.1.30 or newer (Tested on AWS CLI 2.1.30)

CloudQ Agent
- OS: Linux compatible OS (Tested on CentOS 7.5 and Amazon Linux 2)
- Python: 3.8 or newer (Tested on Python 3.8.7)
- AWS CLI: 2.1.30 or newer (Tested on AWS CLI 2.1.30)

CloudQ Builder for AWS
- OS: Linux, MacOS and Windows
- Python: 3.8 or newer (Tested on Python 3.8.7)
- AWS CLI: 2.1.30 or newer (Tested on AWS CLI 2.1.30)
- AWS ParallelCluster: 3.0.3


## Installation

[Installation Guide](/docs/INSTALLATION_GUIDE.md) describes how to install and configure CloudQ.

The following documents describe how to setup CloudQ environment in a specific scenario.

1. [Use ABCI](/docs/EXAMPLE_ABCI.md)
   - Use ABCI as the compute resource and ABCI Cloud Storage as the job storage.

2. [Use AWS](/docs/EXAMPLE_AWS.md)
   - Use AWS as the compute resource and the job storage.

3. Use ABCI and AWS (coming soon)
   - Use ABCI and AWS as the compute resources and ABCI Cloud Storage as the job storage.


## Usage

### Agent

In an environment where CloudQ Agent does not run automatically, you need to launch CloudQ Agent as follows.

```console
$ cloudqd --daemon
```

On compute clusters built by Builder for AWS, CloudQ Agent automatically starts.

### Client

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

The following example display log messages of an CloudQ Agent.

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

### Builder for AWS

CloudQ Builder for AWS is provided as `cloudqaws` command.
It uses AWS default profile to build a cluster.
Be aware that the AWS default profile is properly set.

#### Create a Cluster

`cloudqaws create` creates a cluster on AWS.
Before creating a cluster, you need to set up an SSH key pairs to log in to the cluster head node.

```console
$ cloudqaws create --name your-cluster-name \
                   --keypair YOUR-KEYPAIR-NAME \
                   --cs_profile abci --cs_endpoint https://s3.abci.ai \
                   --cs_bucket cloudq
The stack (your-cluster-name-vpc) is creating. Please wait a minute.
The stack (your-cluster-name-nodes) is creating. Please wait a minute.
AWS compute cluster (your-cluster-name) has been created.
```

#### List Clusters

`cloudqaws list` shows you status of compute clusters you requested to create.

```console
$ cloudqaws list
Cluster Name     Status     Creation Time
---------------------------------------------------
your-cluster-01  COMPLETED  2022/01/23 11:22:33 UTC
your-cluster-02  COMPLETED  2022/02/01 23:59:59 UTC
your-cluster-03  CREATING
your-cluster-04  FAILED
```

#### Delete a Cluster

```console
$ cloudqaws delete --name your-cluster-name
The stack (your-cluster-name-nodes) is deleting. Please wait a minute.
The stack (your-cluster-name-vpc) is deleting. Please wait a minute.
AWS compute cluster (your-cluster-name) has been deleted.
```


## Meta Jobscript

Meta jobscript is introduced to write a jobscript that runs on any systems CloudQ supports.
A jobscript written in Meta jobscript is converted to a local jobscript by a CloudQ agent when it receives a job.
Meta jobscript can use the following directives, functions and environment variables.

### Directives

|  Name  |  Explanation  | ABCI | AWS Compute Cluster |
| ---- | ---- | ---- | ---- |
|  run_on  |  [Optional] Name of a system that runs the job. If not specified, the job will be executed on the earliest scheduled system.  | Available | Available |
|  project  |  [Mandatory] Name of a research project.  It can be used for charge on some systems.  | Available | Unavailable |
|  resource  |  [Mandatory] Name of resource type used to run the job.  | Available | Available |
|  n_resource  |  [Mandatory] Number of resources used to run the job.  | Available | Available |
|  walltime  |  [Optional] Walltime requested.  If not specified, the default walltime on the system is applied.  | Available | Available |
|  other_opts  |  [Optional] Options to the job submission command appended when the job is submitted.  | Available | Available |
|  container_img  |  [Optional] URL of container image used in the job.  It can be specified multiple times.  | Available | Unavailable |

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

Availability
- ABCI: Available
- AWS Compute Cluster: Unavailable

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

Availability
- ABCI: Available
- AWS Compute Cluster: Available

### Environment Variables

|  Name  |  Explanation  | ABCI | AWS Compute Cluster |
| ---- | ---- | ---- | ---- |
|  SYSTEM  |  Name of a system that runs the job.  | Available | Available |
|  CONTAINER_IMG#  |  File name of a container image.  # will be replaced by a serial number starting with 0.  | Available | Unavailable |
|  ARY_TASK_ID  |  Task ID of an array job.  | Available | Available |
|  ARY_TASK_FIRST  |  Task ID of the first task of an array job.  | Available | Available |
|  ARY_TASK_LAST  |  Task ID of the last task of an array job.  | Available | Available |
|  ARY_TASK_STEPSIZE  |  Step size of IDs of an array job.  | Available | Available |

### Example

Example meta jobscripts can be found in `cloudq/example` directory.

- mjob_array.sh
  - Array job example
- mjob_pt_mnist.sh
  - Download container image from NGC and then train MNIST using PyTorch on a singularity container
- mjob_tf_mnist.sh
  - Download container image from NGC and then train MNIST using TensorFlow on a singularity container

## Publications

- Shinichiro Takizawa Masaaki Shimizu, Hidemoto Nakada, Toshiya Matsuba, and Ryousei Takano, "CloudQ: A Secure AI / HPC Cloud Bursting System,"  9th International Workshop on HPC User Support Tools (HUST22), November 2022.