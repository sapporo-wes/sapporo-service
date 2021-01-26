{
    "$graph": [
        {
            "class": "CommandLineTool",
            "requirements": [
                {
                    "dockerPull": "quay.io/biocontainers/fastqc:0.11.9--0",
                    "class": "DockerRequirement"
                }
            ],
            "baseCommand": "fastqc",
            "arguments": [
                {
                    "position": 0,
                    "prefix": "-o",
                    "valueFrom": "."
                }
            ],
            "inputs": [
                {
                    "type": "File",
                    "inputBinding": {
                        "position": 2
                    },
                    "id": "#fastqc.cwl/fastq"
                },
                {
                    "type": [
                        "null",
                        "int"
                    ],
                    "default": 2,
                    "inputBinding": {
                        "position": 1,
                        "prefix": "--threads"
                    },
                    "id": "#fastqc.cwl/nthreads"
                }
            ],
            "outputs": [
                {
                    "type": "File",
                    "outputBinding": {
                        "glob": "*_fastqc.html"
                    },
                    "id": "#fastqc.cwl/qc_result"
                },
                {
                    "type": "stderr",
                    "id": "#fastqc.cwl/stderr"
                },
                {
                    "type": "stdout",
                    "id": "#fastqc.cwl/stdout"
                }
            ],
            "stdout": "fastqc-stdout.log",
            "stderr": "fastqc-stderr.log",
            "id": "#fastqc.cwl"
        },
        {
            "class": "Workflow",
            "inputs": [
                {
                    "type": "File",
                    "id": "#main/fastq_1"
                },
                {
                    "type": "File",
                    "id": "#main/fastq_2"
                },
                {
                    "type": [
                        "null",
                        "int"
                    ],
                    "default": 2,
                    "id": "#main/nthreads"
                }
            ],
            "steps": [
                {
                    "run": "#fastqc.cwl",
                    "in": [
                        {
                            "source": "#main/fastq_1",
                            "id": "#main/qc_1/fastq"
                        },
                        {
                            "source": "#main/nthreads",
                            "id": "#main/qc_1/nthreads"
                        }
                    ],
                    "out": [
                        "#main/qc_1/qc_result",
                        "#main/qc_1/stdout",
                        "#main/qc_1/stderr"
                    ],
                    "id": "#main/qc_1"
                },
                {
                    "run": "#fastqc.cwl",
                    "in": [
                        {
                            "source": "#main/fastq_2",
                            "id": "#main/qc_2/fastq"
                        },
                        {
                            "source": "#main/nthreads",
                            "id": "#main/qc_2/nthreads"
                        }
                    ],
                    "out": [
                        "#main/qc_2/qc_result",
                        "#main/qc_2/stdout",
                        "#main/qc_2/stderr"
                    ],
                    "id": "#main/qc_2"
                },
                {
                    "run": "#trimmomatic_pe.cwl",
                    "in": [
                        {
                            "source": "#main/fastq_1",
                            "id": "#main/trimming/fastq_1"
                        },
                        {
                            "source": "#main/fastq_2",
                            "id": "#main/trimming/fastq_2"
                        },
                        {
                            "source": "#main/nthreads",
                            "id": "#main/trimming/nthreads"
                        }
                    ],
                    "out": [
                        "#main/trimming/trimmed_fastq1P",
                        "#main/trimming/trimmed_fastq1U",
                        "#main/trimming/trimmed_fastq2P",
                        "#main/trimming/trimmed_fastq2U",
                        "#main/trimming/stdout",
                        "#main/trimming/stderr"
                    ],
                    "id": "#main/trimming"
                }
            ],
            "outputs": [
                {
                    "type": "File",
                    "outputSource": "#main/qc_1/qc_result",
                    "id": "#main/qc_result_1"
                },
                {
                    "type": "File",
                    "outputSource": "#main/qc_2/qc_result",
                    "id": "#main/qc_result_2"
                },
                {
                    "type": "File",
                    "outputSource": "#main/trimming/trimmed_fastq1P",
                    "id": "#main/trimmed_fastq1P"
                },
                {
                    "type": "File",
                    "outputSource": "#main/trimming/trimmed_fastq1U",
                    "id": "#main/trimmed_fastq1U"
                },
                {
                    "type": "File",
                    "outputSource": "#main/trimming/trimmed_fastq2P",
                    "id": "#main/trimmed_fastq2P"
                },
                {
                    "type": "File",
                    "outputSource": "#main/trimming/trimmed_fastq2U",
                    "id": "#main/trimmed_fastq2U"
                }
            ],
            "id": "#main"
        },
        {
            "class": "CommandLineTool",
            "requirements": [
                {
                    "dockerPull": "quay.io/biocontainers/trimmomatic:0.38--1",
                    "class": "DockerRequirement"
                }
            ],
            "baseCommand": "trimmomatic",
            "arguments": [
                {
                    "position": 0,
                    "valueFrom": "PE"
                },
                {
                    "position": 4,
                    "valueFrom": "$(inputs.fastq_1.nameroot).trimmed.1P.fq"
                },
                {
                    "position": 5,
                    "valueFrom": "$(inputs.fastq_1.nameroot).trimmed.1U.fq"
                },
                {
                    "position": 6,
                    "valueFrom": "$(inputs.fastq_1.nameroot).trimmed.2P.fq"
                },
                {
                    "position": 7,
                    "valueFrom": "$(inputs.fastq_1.nameroot).trimmed.2U.fq"
                },
                {
                    "position": 8,
                    "valueFrom": "ILLUMINACLIP:/usr/local/share/trimmomatic/adapters/TruSeq2-PE.fa:2:40:15"
                },
                {
                    "position": 9,
                    "valueFrom": "LEADING:20"
                },
                {
                    "position": 10,
                    "valueFrom": "TRAILING:20"
                },
                {
                    "position": 11,
                    "valueFrom": "SLIDINGWINDOW:4:15"
                },
                {
                    "position": 12,
                    "valueFrom": "MINLEN:36"
                }
            ],
            "inputs": [
                {
                    "type": "File",
                    "inputBinding": {
                        "position": 2
                    },
                    "id": "#trimmomatic_pe.cwl/fastq_1"
                },
                {
                    "type": "File",
                    "inputBinding": {
                        "position": 3
                    },
                    "id": "#trimmomatic_pe.cwl/fastq_2"
                },
                {
                    "type": [
                        "null",
                        "int"
                    ],
                    "default": 2,
                    "inputBinding": {
                        "position": 1,
                        "prefix": "-threads"
                    },
                    "id": "#trimmomatic_pe.cwl/nthreads"
                }
            ],
            "outputs": [
                {
                    "type": "stderr",
                    "id": "#trimmomatic_pe.cwl/stderr"
                },
                {
                    "type": "stdout",
                    "id": "#trimmomatic_pe.cwl/stdout"
                },
                {
                    "type": "File",
                    "outputBinding": {
                        "glob": "$(inputs.fastq_1.nameroot).trimmed.1P.fq"
                    },
                    "id": "#trimmomatic_pe.cwl/trimmed_fastq1P"
                },
                {
                    "type": "File",
                    "outputBinding": {
                        "glob": "$(inputs.fastq_1.nameroot).trimmed.1U.fq"
                    },
                    "id": "#trimmomatic_pe.cwl/trimmed_fastq1U"
                },
                {
                    "type": "File",
                    "outputBinding": {
                        "glob": "$(inputs.fastq_1.nameroot).trimmed.2P.fq"
                    },
                    "id": "#trimmomatic_pe.cwl/trimmed_fastq2P"
                },
                {
                    "type": "File",
                    "outputBinding": {
                        "glob": "$(inputs.fastq_1.nameroot).trimmed.2U.fq"
                    },
                    "id": "#trimmomatic_pe.cwl/trimmed_fastq2U"
                }
            ],
            "stdout": "trimmomatic-pe-stdout.log",
            "stderr": "trimmomatic-pe-stderr.log",
            "id": "#trimmomatic_pe.cwl"
        }
    ],
    "cwlVersion": "v1.0"
}