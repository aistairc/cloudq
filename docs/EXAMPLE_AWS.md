# Setup Guide for AWS

This document describes a procedure for installing and configuring CloudQ so that a compute cluster on AWS is used as a cloud compute resource and Amazon S3 is used as the job storage.

![Setup on AWS](/docs/fig_setup_aws.png)

We set the following assumptions.

- You have your AWS account (IAM user)
- AWS CLI is already installed on your work station (PC)
- Your PC satisfies CloudQ requirements
- CloudQ Client and Builder for AWS will be installed on your PC
- You will use CloudQ Builder for AWS to create the compute cluster on AWS
- You will use AWS Tokyo region (ap-northeast-1)
- You will use a cluster with the following configuration
  - CloudQ default VPC
  - eight `t2.micro` instances and eight `t2.small` instances at maximum

For detail about installation and configuration, refer to the [installation guide](/docs/INSTALLATION_GUIDE.md).


## Setup Procedure on your PC

1. Setup AWS profile

   You need to specify two prifiles.
   One is the default profile which is used in CloudQ Builder for AWS.
   The other is a profile used for accessing Amazon S3 for job data.
   The latter profile is configured as `cloudq_job` in the following example.

   ```console
   $ aws configure                         # Set up default profile
   AWS Access Key ID [None]: <YOUR INPUT>
   AWS Secret Access Key [None]: <YOUR INPUT>
   Default region name [None]: ap-northeast-1
   Default output format [None]: <YOUR INPUT>

   $ aws configure --profile cloudq_job    # Set up profile for job data
   AWS Access Key ID [None]: <YOUR INPUT>
   AWS Secret Access Key [None]: <YOUR INPUT>
   Default region name [None]: ap-northeast-1
   Default output format [None]: <YOUR INPUT>
   ```

2. Create a job bucket for CloudQ

   The following example creates the bucket having a URL `s3://cloudq-xxxxx`.
   The URL must be unique.
   AWS endpoint URL has to be properly set because you use Tokyo region.
   AWS endpoint URL for Tokyo region is `s3.ap-northeast-1.amazonaws.com` which is shown in [this page](https://docs.aws.amazon.com/general/latest/gr/s3.html).

   ```console
   $ aws --endpoint-url https://s3.ap-northeast-1.amazonaws.com s3 mb s3://cloudq-xxxxx
   ```

3. Create a SSH key pair for accessing the head node of AWS compute cluster

   The following example creates the key pair as `aws_cloudq`.
   The name of the key pair must be unique in your AWS account.

   ```console
   $ aws ec2 create-key-pair --key-name aws_cloudq --query 'KeyMaterial' \
   --output text > ~/.ssh/aws_cloudq.pem
   $ chmod 400 ~/.ssh/aws_cloudq.pem
   ```

4. Install CloudQ

   ```console
   $ python -m venv ~/cloudq
   $ . ~/cloudq/bin/activate
   (cloudq) $ pip install --upgrade pip setuptools
   (cloudq) $ pip install 'cloudq[aws]'
   ```

   As CloudQ Builder for AWS internally uses [AWS ParallelCluster](https://github.com/aws/aws-parallelcluster), you also need to install Node.js on which AWS ParallelCluster depends.

5. Create preset

   You can create presets of your cluster configurations.
   One your create a preset, you can create clusters with the same configuration defined in the preset anytime.

   ```console
   $ cloudqaws preset --preset_name your_preset_name
   ```

   CloudQ provides following example presets.

   - `enable_docker`: Create AWS Compute Cluster with Docker and Singularity available at compute node.
   - `enable_gpu`: Create AWS Compute Cluster that can execute CUDA with GPGPU at compute node.

   To use them, copy the presets to the CloudQ configuration directory as follows.

   ```console
   $ cd `pip3 show cloudq | grep Location | cut -d ' ' -f 2`/cloudq/aws/example
   $ cp -r preset-name $HOME/.cloudq/aws/
   ```

6. Edit configuration files of the preset

   Configuration files of your preset are stored in `$HOME/.cloudq/aws/your_preset_name`.
   Edit following files to change the configuration of your AWS clusters.

   - `cloud-stack.yaml`: To change VPC configuration or security group
   - `cluster-config.yaml`: To change the settings of the cluster created by AWS Parallel Cluster
   - `on-head-node-start.sh`: To change the procedures when cluster head node starts
   - `on-compute-node-start.sh`: To change the procedures when cluster compute nodes start

   The following example creates a cluster with two types of instances: `t2.micro` and `t2.small`.
   For this purpuse, you need to edit `$HOME/.cloudq/aws/your_preset_name/cluster-config.yaml`.

   ```yaml
   (snip)
   Scheduling:
     Scheduler: slurm
     SlurmQueues:
     - Name: queue1
       ComputeResources:
       - Name: t2micro
         InstanceType: t2.micro
         MinCount: 0
         MaxCount: 8
       - Name: t2small            # Add this line
         InstanceType: t2.small   # Add this line
         MinCount: 0              # Add this line
         MaxCount: 8              # Add this line
   (snip)
   ```

7. Edit configuration files of your CloudQ Client

   Edit `default` section of `$HOME/.cloudq/client/config.ini`.

   ```ini
   [default]
   # specify your pc name
   name = your_pc

   # specify the AWS profile you created
   aws_profile = cloudq_job

   # specify S3 Tokyo region endpoint
   cloudq_endpoint_url = https://s3.ap-northeast-1.amazonaws.com
   # Speicfy the bucket
   cloudq_bucket = cloudq-xxxxx
   ```

   To use meta jobscripts, you also need to edit `$HOME/.cloudq/client/resource.ini`.
   On AWS, a resource in CloudQ corresponds to an instance type.
   The key must be the name of cluster you will create.
   The following example, the name of the cluster is set as `your_aws_cluster`.

   ```ini
   [resource001]
   your_aws_cluster = t2.micro

   [resource002]
   your_aws_cluster = t2.small
   ```

8. Create your AWS cluster

   The following example creates a cluster named `your_aws_cluster` with the above configuration.
   The cluster name must be unique in your AWS account.

   ```console
   (cloudq) $ cloudqaws create --preset_name your_preset_name \
   --name your_aws_cluster \
   --keypair aws_cloudq \
   --cs_profile cloudq_job \
   --cs_endpoint https://s3.ap-northeast-1.amazonaws.com \
   --cs_bucket cloudq-xxxxx
   ```

   The creation takes several minutes to complete.
   After completion you can check the status of your cluster.

   ```console
   (cloudq) $ cloudqaws list
   Cluster Name    Status     Creation Time
   --------------------------------------------------
   your_aws_clust  COMPLETED  YYYY/MM/DD hh:mm:ss UTC
   ```

   You can ssh login to the cluster head node.

   ```console
   (cloudq) $ pcluster ssh --cluster-name your_aws_cluster -i ~/.ssh/aws_cloudq.pem
   ```

   You can also check logs on Amazon CloudWatch Logs.

9. Use your AWS cluster

   As CloudQ recognize your AWS cluster as `your_aws_cluster`, you need to specify the name when you submit a job.
   The following exmaple submits a local job script.

   ```console
   (cloudq) $ cloudqcli submit --script job.sh --submit_to your_aws_cluster
   ```

10. Stop your AWS cluster

    After you use your AWS cluster you can stop it if you no more use it.

    ```console
    (cloudq) $ cloudqaws delete --name your_aws_cluster
    ```
