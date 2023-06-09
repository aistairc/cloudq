# Meta Jobscript Description

This document describes how to use Meta jobscript.

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
