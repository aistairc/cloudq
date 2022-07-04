# CloudQ Installation Guide

## Installation

### CloudQ Client

CloudQ Client needs to be installed on computers where you submit jobs.

Install from PyPI.

```console
$ pip install cloudq
```

Install from GitHub.

```console
$ git clone git@github.com:aistairc/cloudq.git
$ cd cloudq
$ pip install -r requirements.txt
$ pip install .
```

### CloudQ Agent

A CloudQ Agent needs to be installed on a server on which the Agent can submit jobs to the system you want to use.

To install Agent, you need to specify one of the optional dependencies for a system where you use CloudQ: `abci`.

Below is an example to install CloudQ Agent for ABCI.

```console
$ pip install 'cloudq[abci]'
```

Install from GitHub.

```console
$ git clone git@github.com:aistairc/cloudq.git
$ cd cloudq
$ pip install -r requirements.txt
$ pip install -r requirements_abci.txt
$ pip install .
```

### CloudQ Builder for AWS

CloudQ Builder for AWS creates compute clusters on AWS which can be used as CloudQ resources.
It needs to be installed on computers where you manage the clusters.

Install from PyPI.

```console
$ pip install 'cloudq[aws]'
```

Install from GitHub.

```console
$ git clone git@github.com:aistairc/cloudq.git
$ cd cloudq
$ pip install -r requirements.txt
$ pip install -r requirements_aws.txt
$ pip install .
```

As CloudQ Builder for AWS internally uses [AWS ParallelCluster](https://github.com/aws/aws-parallelcluster), you also need to install Node.js on which AWS ParallelCluster depends.


## Configure CloudQ

### Procedure for Changing Configuration

To change the configuration after installation, you need to edit configuration files under the installed package directory.

- `(package directory)/cloudq/data/`: Configuration files for Client and Agent
- `(package directory)/cloudq/aws/data/`: Configuration files for Builder for AWS

The path of the package directory can be found by the following command.

```console
$ pip show cloudq
```

You can open to edit `(package directory)/cloudq/data/config.ini` by the following command.

```console
$ vi `pip show cloudq | grep Location | cut -d ' ' -f 2`/cloudq/data/config.ini
```

### Client Configuration

You need to edit `default` section of `(package directory)/cloudq/data/config.ini`.

```ini
[default]
name = your_system_name

aws_profile = default

cloudq_endpoint_url = https://s3.abci.ai
cloudq_bucket = cloudq
```

- **name**: name of the server you use CloudQ Client
- **aws_profile**: AWS profile used for accessing the job bucket
- **cloudq_endpoint_url**: endpoint URL of the object storage
- **cloudq_bucket**: name of the job bucket

If you want to use meta jobscripts, you also need to edit two meta jobscript configuration files.

One is the project definition file whose path is `(package directory)/cloudq/data/project.ini`.
A project is used to define a research project and it can be used for resource authorization or charge on systems.

This is an example configuration of the project definition file.

```ini
[project001]
abci = YOURPROJECT1
awscluster01 = IGNORED

[project002]
abci = YOURPROJECT2
awscluster01 = IGNORED
```

`project001` and `project002` are names of projects used in meta jobscripts, followed by definitions of project names on each system.
The following table shows the rule of how to specify key and project names for each system.

| System | Key Name          | Project Name     |
| :------| :---------------- | :--------------- |
| ABCI   | abci              | ABCI group name  |
| AWS    | your cluster name | value is ignored |

The other is the resource definition file whose path is `(package directory)/cloudq/data/resource.ini`.
A resource is a type of server on which your jobs run.

This is an example configuration of the resource definition file.

```ini
[resource001]
abci = RESOURCETYPE1
awscluster01 = INSTANCETYPE1

[resource002]
abci = RESOURCETYPE2
awscluster01 = INSTANCETYPE1
```

`resource001` and `resource002` are names of resources in meta jobscripts, followed by definitions of resource types on each system.
The following table shows the rule of how to specify key and resource names for each system.

| System | Key Name          | Resource Name      |
| :----- | :---------------- | :----------------- |
| ABCI   | abci              | ABCI resource type |
| AWS    | your cluster name | EC2 instance type  |

### Agent Configuration

You need to edit `default` and `agent` sections of `(package directory)/cloudq/data/config.ini`.

```ini
[default]
name = your_system_name

aws_profile = default

cloudq_endpoint_url = https://s3.abci.ai
cloudq_bucket = cloudq

[agent]
type = abci
num_procs = 8
daemon_interval = 5
cloudq_directory = ~/.cloudq
```

- **default**
  - **name**: name of the server you use CloudQ Client
  - **aws_profile**: AWS profile used for accessing the job bucket
  - **cloudq_endpoint_url**: endpoint URL of the object storage
  - **cloudq_bucket**: name of the job bucket
- **agent**
  - **type**: scheduler type. `abci` and `slurm` are supported.
  - **num_procs**: number of processes that submit jobs to the system
  - **daemon_interval**: time interval in seconds at which Agent checks jobs in the job bucket
  - **cloudq_directory**: a directory where jobs and logs are stored

### Builder Configuration

You need to edit several files under `(package directory)/cloudq/aws/data` directory depending on what cluster you want to create.

- **cloud-stack.yaml**: To change configurations of the VPC and security groups
- **cluster-config.yaml**: To change the configuration of the cluster. It is a YAML file of AWS ParallelCluster configuration.
- **on-head-node-start.sh**: To run some commands during the initialization of the cluster head node
- **on-compute-node-start.sh**: To run some commands during the initialization of compute nodes
