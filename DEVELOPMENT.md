# Development Notes of CloudQ Agent

Copyright 2022 National Institute of Advanced Industrial Science and Technology (AIST), Japan and
Hitachi, Ltd.


# Architecture of CloudQ
CloudQ consists of **Client** and **Agent**.
Client runs on the user terminal and Agent runs on the front-end node of its target system.
Client and Agent exchange job input and output through cloud storage.

## Role of CloudQ Client
CloudQ Client downloads and uploads data to the cloud storage upon receiving commands from the user.

It provides following functions:
- Submit and cancel jobs.
- Retrieve job status and execution records.
- Download job execution results.
- Delete job data on the cloud storage.

## Role of CloudQ Agent
CloudQ Agent retrieves job data stored in a cloud storage and executes jobs in the local scheduler of the system.

It provides following functions:
- Receive jobs submitted by CloudQ Client.
- If the received job is a meta jobscript, convert it to a local jobscript.
- Submit the job to the local scheduler of the system.
- Check the status of the job submitted to the local scheduler and upload it to the cloud storage.


# How to Delvelop CloudQ Agent for a Specific System
In order to develop CloudQ Agent for a specific system, the developer needs to do the following:
1. Create a system-specific implementation class that inherits from the provided job management IF.
2. Create a system-specific implementation class that inherits from the provided meta jobscript conversion IF.
3. Register the implemented class by referring to [How to Add Support for a Specific System](#how-to-add-support-for-a-specific-system).


# Job Management IF
## Feature
This interface is provided for easy development of CloudQ job manager for a specific system.
A class that inherits this interface and properly implement abstract methods manages jobs under CloudQ job management rules.

## Abstract Class Name
AbstractJobManager

## Properties
### Target System Name

```python
    def SYSTEM_NAME(self):
```

Return the name of the target system.

## Methods
### Submit a Job

```python
    def submit_job(self, manifest):
```

Arguments
- manifest dict[str, obj]: Contents of the job manifest

Returns
- dict[str, obj]: Contents of the job manifest after submission

This method submits a job to the local scheduler.
It submits a job indicated by `manifest` to the local scheduler, and returns the manifest with job ID, the local group name and the job submission command in the local scheduler as the execution result.
When an error occurs, the manifest with the error message should be returned.

This method should be called in the job working directory, and the script file is assumed to be stored in the job working directory.

### Get the Status of Jobs

```python
    def get_jobs_status(self):
```

Returns
- dict[str, str]: Status list of all jobs registered in the local scheduler by the agent.

This method obtains the status of jobs from the local scheduler and returns them as a dictionary in which job ID is key and the job status is value.
It should return the status of all jobs that have been submitted to the local scheduler using the agent's account and have not yet been terminated.
A job whose status is not returned by this method is considered to have been normally terminated.

### Cancel a Job

```python
    def cancel_job(self, manifest, force=False):
```

Arguments
- manifest dict[str, obj]: Contents of the job manifest
- force bool: Whether to force cancellation or not

Returns
- dict[str, obj]: Contents of the job manifest after execution

This method requests the local scheduler cancel a job.
The job to be canceled is described in `manifest`.
If `force` is true, it requests forcibly cancel the job.
When an error occurs, the manifest with the error message should be returned.

### Get Job Logs

```python
    def get_job_log(self, manifest, error=False):
```

Arguments
- manifest dict[str, obj]: Contents of the job manifest

Returns
- dict[str, obj]: Contents of the job manifest after execution

This method obtains the standard output or standard error output of a job from the local scheduler and writes them to files in the job working directory.
The output file name should be `stdout` for standard output and `stderr` for standard error output.
If there are multiple files of standard output or standard error output for a job, it adds `. (serial number)` as suffixes to the files.
The serial number is a unique number that distinguishes each file.
When an error occurs, the manifest with the error message must be returned.


# Meta Jobscript Conversion IF
## Feature
This interface is provided for easy development of CloudQ meta jobscript converter for a specific system.
A class that inherits this interface and properly implement abstract methods converts meta jobscripts under CloudQ rules.

## Abstract Class Name
AbstractMetaJobScriptConverter

## Properties

```python
    def SYSTEM_NAME(self):
```
Return the name of the target sytem.

## Methods
### Convert to Local Jobscript

```python
    def to_local_job_script(self, manifest, endpoint_url, aws_profile):
```

Arguments
- manifest dict[str, obj]: Contents of the job manifest
- endpoint_url str: Endpoint URL of cloud storage
- aws_profile str: Name of AWS profile

Returns
- dict[str, obj]: Contents of the job manifest after execution

This method converts a meta jobscript to a local jobscript and saves it in the job working directory.
If the converted log jobscript file name is used in the job management function IF, it should be added to the manifest.
When an error occurs, return the manifest with the error message added.

This method should be called in the job working directory, and the script file before conversion should be stored in the job working directory.


# Job Manifest
The contents described in the manifest file are listed below:

|  Name  |  Explanation  |
| ---- | ---- |
|  uuid  |  Job ID in CloudQ.  |
|  jobid  |  Job ID in the local scheduler.  |
|  name  |  Script file name.  |
|  jobscript_type  |  Type of jobscript.<br>`local` means local jobscript. `meta` means meta jobscript.  |
|  hold_jid  |  Job ID of a dependent job.<br>Dependent job is a job that must be completed before this job can be executed.  |
|  array_tid  |  Task ID of an array job.  |
|  submit_to  |  System name specified by the user to execute this job.  |
|  submit_opt  |  Options specified by the user to be used when executing this job.  |
|  state  |  State of job progress.  |
|  workdir  |  Path of job working directory.  |
|  run_system  |  Name of the system on which the job was executed.  |
|  local_account  |  Account name specified at job execution.  |
|  local_group  |  Group name specified at job execution.  |
|  submit_command  |  Job submission command to the local scheduler.  |
|  time_submit  |  Timestamp when the client submitted the job.  |
|  time_receive  |  Timestamp when the job was accepted by the agent.  |
|  time_ready  |  Timestamp when the job moves to the state `waiting` for execution in the local scheduler.  |
|  time_start  |  Timestamp when the job starts in the local scheduler.  |
|  time_stageout_start  |  Timestamp when the output data upload was started.  |
|  time_stageout_finish  |  Timestamp when the output data upload was completed.  |
|  time_finish  |  Timestamp when the job ended in the local scheduler.  |
|  size_input  |  File size of jobscript.  |
|  size_output  |  File size of output data.  |
|  error_msg  |  Message that notifies errors.  |


# How to Add Support for a Specific System
The developer should edit the following parts of `cloudq/interface.py`.

```python
# Import job manager module
import job_manager_for_your_system

# Import meta jobscript converter module
import meta_jobscript_converter_for_your_system

JOB_MANAGER_IMPL_LIST = [
    # add class name of job manager for your system
    YourSystemJobManager
]

META_JOB_SCRIPT_CONVERTER_IMPL_LIST = [
    # add class name of meta jobscript converter for your system
    YourSystemMetaJobScriptConverter
]
```


# How to Remove Support for a Specific System
The developer should edit `cloudq/interface.py` to delete the import statement and class name added in [How to Add Support for a Specific System](#how-to-add-support-for-a-specific-system).
