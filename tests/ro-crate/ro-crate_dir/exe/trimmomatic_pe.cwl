#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: CommandLineTool
requirements:
  DockerRequirement:
    dockerPull: quay.io/biocontainers/trimmomatic:0.38--1
baseCommand: trimmomatic
arguments:
  - position: 0
    valueFrom: PE
  - position: 4
    valueFrom: $(inputs.fastq_1.nameroot).trimmed.1P.fq
  - position: 5
    valueFrom: $(inputs.fastq_1.nameroot).trimmed.1U.fq
  - position: 6
    valueFrom: $(inputs.fastq_1.nameroot).trimmed.2P.fq
  - position: 7
    valueFrom: $(inputs.fastq_1.nameroot).trimmed.2U.fq
  - position: 8
    valueFrom: ILLUMINACLIP:/usr/local/share/trimmomatic/adapters/TruSeq2-PE.fa:2:40:15
  - position: 9
    valueFrom: LEADING:20
  - position: 10
    valueFrom: TRAILING:20
  - position: 11
    valueFrom: SLIDINGWINDOW:4:15
  - position: 12
    valueFrom: MINLEN:36

inputs:
  nthreads:
    type: int?
    default: 2
    inputBinding:
      position: 1
      prefix: -threads
  fastq_1:
    type: File
    inputBinding:
      position: 2
  fastq_2:
    type: File
    inputBinding:
      position: 3

outputs:
  trimmed_fastq1P:
    type: File
    outputBinding:
      glob: $(inputs.fastq_1.nameroot).trimmed.1P.fq
  trimmed_fastq1U:
    type: File
    outputBinding:
      glob: $(inputs.fastq_1.nameroot).trimmed.1U.fq
  trimmed_fastq2P:
    type: File
    outputBinding:
      glob: $(inputs.fastq_1.nameroot).trimmed.2P.fq
  trimmed_fastq2U:
    type: File
    outputBinding:
      glob: $(inputs.fastq_1.nameroot).trimmed.2U.fq
  stdout: stdout
  stderr: stderr
stdout: trimmomatic-pe-stdout.log
stderr: trimmomatic-pe-stderr.log
