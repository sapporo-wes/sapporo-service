#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: CommandLineTool
requirements:
  DockerRequirement:
    dockerPull: quay.io/biocontainers/fastqc:0.11.9--0
baseCommand: fastqc
arguments:
  - position: 0
    prefix: -o
    valueFrom: .

inputs:
  nthreads:
    type: int?
    default: 2
    inputBinding:
      position: 1
      prefix: --threads
  fastq:
    type: File
    inputBinding:
      position: 2

outputs:
  qc_result:
    type: File
    outputBinding:
      glob: "*_fastqc.html"
  stdout: stdout
  stderr: stderr
stdout: fastqc-stdout.log
stderr: fastqc-stderr.log
