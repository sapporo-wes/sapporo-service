#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: Workflow
inputs:
  fastq_1:
    type: File
  fastq_2:
    type: File
  nthreads:
    type: int?
    default: 2

steps:
  qc_1:
    run: ./fastqc.cwl
    in:
      nthreads: nthreads
      fastq: fastq_1
    out:
      - qc_result
      - stdout
      - stderr
  qc_2:
    run: ./fastqc.cwl
    in:
      nthreads: nthreads
      fastq: fastq_2
    out:
      - qc_result
      - stdout
      - stderr
  trimming:
    run: ./trimmomatic_pe.cwl
    in:
      nthreads: nthreads
      fastq_1: fastq_1
      fastq_2: fastq_2
    out:
      - trimmed_fastq1P
      - trimmed_fastq1U
      - trimmed_fastq2P
      - trimmed_fastq2U
      - stdout
      - stderr

outputs:
  qc_result_1:
    type: File
    outputSource: qc_1/qc_result
  qc_result_2:
    type: File
    outputSource: qc_2/qc_result
  trimmed_fastq1P:
    type: File
    outputSource: trimming/trimmed_fastq1P
  trimmed_fastq1U:
    type: File
    outputSource: trimming/trimmed_fastq1U
  trimmed_fastq2P:
    type: File
    outputSource: trimming/trimmed_fastq2P
  trimmed_fastq2U:
    type: File
    outputSource: trimming/trimmed_fastq2U
