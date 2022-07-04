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

   It uses the AWS profile `cloudq_job` to create the bucket.

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

5. Edit configuration files for your AWS cluster

   Edit `Scheduling::SlurmQueues::ComputeResources` section of `(package directory)/cloudq/aws/data/cluster-config.yaml` so that `t2.micro` and `t2.small` instances can be used.

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

6. Edit configuration files for your CloudQ Client

   Edit `default` section of `(package directory)/cloudq/data/config.ini`.

   ```ini
   [default]
   # specify your pc name
   name = your_pc

   # specify the AWS profile
   aws_profile = cloudq_job

   # specify S3 Tokyo region endpoint
   cloudq_endpoint_url = https://s3.ap-northeast-1.amazonaws.com
   # Speicfy the bucket
   cloudq_bucket = cloudq-xxxxx
   ```

   To use meta jobscripts, you also need to edit `(package directory)/cloudq/data/resource.ini`.
   On AWS, a resource in CloudQ corresponds to an instance type.
   The key must be the name of cluster you will create.
   The following example, the name of the cluster is set as `your_aws_cluster`.

   ```ini
   [resource001]
   your_aws_cluster = t2.micro

   [resource002]
   your_aws_cluster = t2.small
   ```

7. Create your AWS cluster

   The following example creates a cluster named `your_aws_cluster` with the above configuration.
   The cluster name must be unique in your AWS account.

   ```console
   (cloudq) $ cloudqaws create --name your_aws_cluster \
   --keypair aws_cloudq \
   --cs_profile cloudq_job \
   --cs_endpoint https://s3.ap-northeast-1.amazonaws.com \
   --cs_bucket cloudq-xxxxx
   ```

   The creation takes several minutes to complete.
   After completion you can check the status of your cluster as follows.

   ```console
   # Check the status of the cluster
   (cloudq) $ cloudqaws list
   # SSH login to the cluster head node
   (cloudq) $ pcluster ssh --cluster-name your_aws_cluster -i ~/.ssh/aws_cloudq.pem
   ```

   You can also check any logs on Amazon CloudWatch Logs.

8. Use your AWS cluster

   As CloudQ recognize your AWS cluster as `your_aws_cluster`, you need to specify the name when you submit a job.
   The following exmaple submits a local job script.

   ```console
   (cloudq) $ cloudqcli submit --script job.sh --submit_to your_aws_cluster
   ```

9. Stop your AWS cluster

   After you use your AWS cluster you can stop it if you no more use it.

   ```console
   (cloudq) $ cloudqaws delete --name your_aws_cluster
   ```

   You you no more use the job bucket and SSH key pair, you can also delete them.
