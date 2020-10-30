# docker build -t manabudockerslurmubuntu:0.3.0 .
#
#FROM ubuntu:18.04
FROM ubuntu:20.04
RUN apt-get update
RUN apt-get install -y slurm-client
RUN apt-get install -y python3 python3-pip
RUN pip3 install toil
RUN pip3 install toil[cwl]

