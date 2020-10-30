#!/bin/bash
#
chmod 777 .
# TODO: JOBTHORWUSERNAME, JOBTRHOWUSERID are injected by parameter
JOB_USERNAME=JOBTHROWUSERNAME
JOB_UID=JOBTHROWUSERID
#JOB_PWD=$4
echo ${JOB_USERNAME}
echo ${JOB_UID}
echo ${JOB_JOBSTORE}


/etc/init.d/munge stop
mv /etc/munge/munge.key /etc/munge/munge.key.org
cp /work/munge/munge.key /etc/munge/
chown munge:munge /etc/munge/munge.key
cp /work/slurm-llnl/slurm.conf /etc/slurm-llnl/
/etc/init.d/munge start
useradd -u ${JOB_UID} ${JOB_USERNAME}
su ${JOB_USERNAME} -c "toil-cwl-runner \
    --setEnv PATH=/home/manabu/work/python/venv/bin \
    --jobStore ./job_Store \
    --batchSystem Slurm \
    --retryCount 2 \
    --maxLogFileSize 20000000000 \
    --stats \
    /home/manabu/work/slurmdocker/docker/example.cwl \
    /home/manabu/work/slurmdocker/docker/example-job.yaml"

