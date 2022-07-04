# Setup Guide for ABCI

This document describes a procedure for installing and configuring CloudQ so that an Agent runs on [ABCI](https://abci.ai/) head node and ABCI Cloud Storage is used as the job storage.

![Setup on ABCI](/docs/fig_setup_abci.png)

We set the following assumptions.

- You have your ABCI account
- You have your ABCI Cloud Storage account
- AWS CLI is already installed on your work station (PC)
- Your PC satisfies CloudQ requirements
- CloudQ Client will be installed on your PC

For detail about installation and configuration, refer to the [installation guide](/docs/INSTALLATION_GUIDE.md).


## Setup Procedure on your PC

1. Setup AWS profile for ABCI Cloud Storage

   The following example configures the AWS profile as `abci`.

   ```console
   $ aws configure --profile abci
   AWS Access Key ID [None]: <YOUR INPUT>
   AWS Secret Access Key [None]: <YOUR INPUT>
   Default region name [None]: <YOUR INPUT>
   Default output format [None]: <YOUR INPUT>
   ```

2. Create a job bucket for CloudQ

   The following example creates the bucket having a URL `s3://cloudq-xxxxx`.
   The URL must be unique.
   It uses the AWS profile `abci` to create the bucket.

   ```console
   $ aws --profile abci --endpoint-url https://s3.abci.ai s3 mb s3://cloudq-xxxxx
   ```

3. Install CloudQ

   ```console
   $ python -m venv ~/cloudq
   $ . ~/cloudq/bin/activate
   (cloudq) $ pip install --upgrade pip setuptools
   (cloudq) $ pip install cloudq
   ```

4. Edit configuration files

   Edit `default` section of `(package directory)/cloudq/data/config.ini`.

   ```ini
   [default]
   # specify your pc name
   name = your_pc

   # specify the AWS profile
   aws_profile = abci

   # specify ABCI Cloud Storage endpoint
   cloudq_endpoint_url = https://s3.abci.ai
   # Speicfy the bucket
   cloudq_bucket = cloudq-xxxxx
   ```

   To use meta jobscripts, edit `(package directory)/cloudq/data/project.ini`.
   On ABCI, a project in CloudQ corresponds to an ABCI group.
   The key must be `abci`.

   ```ini
   [project001]
   abci = gXXYYYYY

   [project002]
   abci = gXXZZZZZ
   ```

   To use meta jobscripts, you also need to edit `(package directory)/cloudq/data/resource.ini`.
   On ABCI, a resource in CloudQ corresponds to a resource type.
   The key must be `abci`.

   ```ini
   [resource001]
   abci = rt_G.small

   [resource002]
   abci = rt_G.large
   ```


## Setup Procedure on ABCI Head Node

1. Setup AWS profile for ABCI Cloud Storage

   The following example configures the AWS profile as `abci`.

   ```console
   [username@es1 ~]$ module load aws-cli
   [username@es1 ~]$ aws configure --profile abci
   AWS Access Key ID [None]: <YOUR INPUT>
   AWS Secret Access Key [None]: <YOUR INPUT>
   Default region name [None]: <YOUR INPUT>
   Default output format [None]: <YOUR INPUT>
   ```

2. Install CloudQ

   ```console
   [username@es1 ~]$ module load gcc/9.3.0 python/3.8
   [username@es1 ~]$ python3 -m venv ~/cloudq
   [username@es1 ~]$ . ~/cloudq/bin/activate
   [username@es1 ~](cloudq) $ pip install --upgrade pip setuptools
   [username@es1 ~](cloudq) $ pip install 'cloudq[abci]'
   ```

3. Edit configuration files

   Edit `default` section of `(package directory)/cloudq/data/config.ini`.

   ```ini
   [default]
   # Specify "abci"
   name = abci

   # specify the AWS profile
   aws_profile = abci

   # specify ABCI Cloud Storage endpoint
   cloudq_endpoint_url = https://s3.abci.ai
   # Speicfy the bucket
   cloudq_bucket = cloudq-xxxxx
   ```

4. Run Agent

   Run Agent on ABCI head node using a terminal multiplexer, such as screen and tmux, so that the Agent can live long.

   ```console
   [username@es1 ~](cloudq) $ screen
   [username@es1 ~](cloudq) $ cloudqd --daemon
   ```
