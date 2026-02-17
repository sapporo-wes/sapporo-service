# RO-Crate

## Overview

[RO-Crate](https://www.researchobject.org/ro-crate/) is a community effort to establish a lightweight approach to packaging research data with their metadata. It is based on [Schema.org](https://schema.org/) annotations in JSON-LD.

After each workflow run completes (or fails at the executor level), sapporo-service automatically generates an `ro-crate-metadata.json` file in the run directory. This metadata captures the full provenance of the run: the workflow executed, input parameters, output files, timestamps, exit codes, and runtime environment, enabling reproducibility and comparison of workflow executions.

## Conformance

The generated RO-Crate metadata conforms to the following specifications:

| Specification | Version | Notes |
|---|---|---|
| RO-Crate | 1.1 | ro-crate-py 0.14.x default |
| WRROC Process Run Crate | 0.5 | Prerequisite for Workflow Run Crate |
| WRROC Workflow Run Crate | 0.5 | sapporo treats engines as black boxes |
| Workflow RO-Crate | 1.0 | Standard ComputationalWorkflow representation |

Provenance Run Crate is out of scope because it requires per-step execution info (`HowToStep`, `ControlAction`, `OrganizeAction`), which sapporo does not have. Sapporo delegates execution to workflow engines as black boxes and does not track individual step-level provenance.

## Generation Conditions

RO-Crate generation is triggered from `run.sh` after the workflow engine finishes. The following table describes when metadata is generated:

| Run State | RO-Crate Generated | Reason |
|---|---|---|
| `COMPLETE` | Yes | Normal success path |
| `EXECUTOR_ERROR` | Yes (`FailedActionStatus`) | Outputs may be absent, but metadata is still valuable |
| `SYSTEM_ERROR` | No | Preconditions not satisfied |
| `CANCELED` | No | Preconditions not satisfied |

If RO-Crate generation itself fails, `run.sh` writes `{"@error": "RO-Crate generation failed. Check stderr.log for details."}` to `ro-crate-metadata.json` and appends the Python error traceback to `stderr.log`. The `@error` key in the response indicates a generation failure, distinguishing it from a valid RO-Crate (which contains `@graph`) or a run where RO-Crate was not generated (which returns `null` via the API).

## Entity Graph

```text
@context: [ro-crate/1.1, wfrun/context, sapporo]

Root Dataset (./)
  +-- conformsTo    -> [process/0.5, workflow/0.5, workflow-ro-crate/1.0]
  +-- mainEntity    -> ComputationalWorkflow
  +-- mentions      -> [CreateAction]
  +-- hasPart       -> [all data entities]
  +-- datePublished -> ISO 8601 datetime

ComputationalWorkflow
  +-- @type: [File, SoftwareSourceCode, ComputationalWorkflow]
  +-- programmingLanguage -> ComputerLanguage
  +-- input  -> [FormalParameter...]
  +-- output -> [FormalParameter...]

CreateAction (#run_id)
  +-- instrument      -> ComputationalWorkflow
  +-- object          -> [File (inputs), PropertyValue (params)]
  +-- result          -> [File (outputs)]
  +-- agent           -> Person (from username.txt)
  +-- executedBy      -> [SoftwareApplication (engine), SoftwareApplication (sapporo)]
  +-- startTime       -> ISO 8601 datetime
  +-- endTime         -> ISO 8601 datetime
  +-- actionStatus    -> CompletedActionStatus | FailedActionStatus
  +-- exitCode        -> int (sapporo context)
  +-- description     -> summary text (e.g., "Executed wf.cwl using cwltool")
  +-- error           -> stderr tail (failure only)
  +-- containerImage  -> ContainerImage
  +-- subjectOf       -> [stdout.log, stderr.log, cmd.txt, system_logs.json, workflow_engine_params.txt]
  +-- multiqcStats    -> File (MultiQC stats)
```

### Root Data Entity

The root dataset includes:

- `name` / `description`: Generated from the run ID.
- `datePublished`: ISO 8601 datetime of when the RO-Crate was generated.
- `license`: A textual note stating that licensing of individual files is determined by their respective owners. The RO-Crate Metadata Descriptor (`ro-crate-metadata.json`) is separately licensed under CC0 1.0.
- `publisher`: Sapporo WES Project organization (the entity that generated and serves this crate).

### Workflow Entity

The `ComputationalWorkflow` entity represents the executed workflow. It conforms to the [Bioschemas ComputationalWorkflow 1.0-RELEASE](https://bioschemas.org/profiles/ComputationalWorkflow/1.0-RELEASE) profile. Supported workflow languages are resolved via `ro-crate-py`:

| Type | Language |
|---|---|
| `CWL` | Common Workflow Language |
| `WDL` | Workflow Description Language |
| `NFL` | Nextflow |
| `SMK` | Snakemake |

### CreateAction

The `CreateAction` entity records the execution provenance:

- **`instrument`**: References the `ComputationalWorkflow`.
- **`object`**: Input files (`workflow_attachment`) and parameters (`workflow_params.json` key-value pairs as `PropertyValue` entities).
- **`result`**: Output files from the `outputs/` directory.
- **`agent`**: A `Person` entity derived from `username.txt` (when authentication is enabled).
- **`executedBy`**: References to `SoftwareApplication` entities for the workflow engine and sapporo.
- **`actionStatus`**: `CompletedActionStatus` (exit code 0) or `FailedActionStatus` (non-zero).
- **`description`**: Summary text (e.g., "Executed wf.cwl using cwltool").
- **`error`**: Last 20 lines of `stderr.log` (failure only).
- **`containerImage`**: Docker image extracted from `cmd.txt` (e.g., `quay.io/commonwl/cwltool:3.1.x`).
- **`subjectOf`**: References to `stdout.log`, `stderr.log`, `cmd.txt`, `system_logs.json`, and `workflow_engine_params.txt`.

## Custom Properties (sapporo context)

Custom properties are defined under the `https://w3id.org/ro/terms/sapporo` context. These properties enable the [Tonkaz](https://github.com/sapporo-wes/tonkaz) workflow comparison tool to perform fine-grained file-level comparison between runs.

| Property | Domain | Description |
|---|---|---|
| `exitCode` | `CreateAction` | Process exit code |
| `executedBy` | `CreateAction` | References to SoftwareApplication entities (engine, sapporo) |
| `lineCount` | `File` | Number of lines in a text file |
| `text` | `File` | Embedded file content (files <= 10 KB) |
| `multiqcStats` | `CreateAction` | Reference to MultiQC general stats JSON |
| `FileStats` | (type) | Type for samtools/vcftools statistics |
| `stats` | `File` | Link from File to FileStats |

File checksums use `sha256` (defined in the wfrun context).

## Bioinformatics Extensions

sapporo automatically runs bioinformatics analysis tools on output files to embed domain-specific statistics in the RO-Crate metadata.

### MultiQC Statistics

[MultiQC](https://multiqc.info/) is run automatically on the entire run directory after workflow completion. If MultiQC finds supported tool outputs (e.g., FastQC, samtools), it generates a `multiqc_general_stats.json` file. This file is:

- Stored at `{run_dir}/multiqc_general_stats.json`.
- Added to the crate as a `File` entity with full content embedded.
- Referenced from the `CreateAction` via the `multiqcStats` property.

### samtools Stats (BAM/SAM)

For output files with BAM (`.bam`) or SAM (`.sam`) format (detected via EDAM ontology), `samtools flagstats` is run in a Docker container (`quay.io/biocontainers/samtools:1.15.1`). The resulting `FileStats` entity includes:

| Property | Description |
|---|---|
| `totalReads` | Total number of reads |
| `mappedReads` | Number of mapped reads |
| `unmappedReads` | Number of unmapped reads |
| `duplicateReads` | Number of duplicate reads |
| `mappedRate` | Mapped reads / total reads |
| `unmappedRate` | Unmapped reads / total reads |
| `duplicateRate` | Duplicate reads / total reads |

### vcftools Stats (VCF)

For output files with VCF format (`.vcf`, `.vcf.gz`), `vcf-stats` is run in a Docker container (`quay.io/biocontainers/vcftools:0.1.16`). The resulting `FileStats` entity includes:

| Property | Description |
|---|---|
| `variantCount` | Total number of variants |
| `snpsCount` | Number of SNPs |
| `indelsCount` | Number of indels |

### EDAM Format Auto-detection

Output files are automatically annotated with [EDAM ontology](http://edamontology.org/) format identifiers based on file extension. EDAM entities use `@type: "Thing"` as they represent ontology terms rather than web resources. Supported extensions include:

| Extension | EDAM Format |
|---|---|
| `.bam` | BAM (`format_2572`) |
| `.sam` | SAM (`format_2573`) |
| `.vcf`, `.vcf.gz` | VCF (`format_3016`) |
| `.fastq`, `.fq`, `.fastq.gz`, `.fq.gz` | FASTQ (`format_1930`) |
| `.fa`, `.fasta` | FASTA (`format_1929`) |
| `.bed` | BED (`format_3003`) |
| `.gtf` | GTF (`format_2306`) |
| `.gff` | GFF3 (`format_1975`) |
| `.bw` | bigWig (`format_3006`) |
| `.bb` | bigBed (`format_3004`) |
| `.wig` | WIG (`format_3005`) |

Common non-bioinformatics formats (JSON, CSV, TSV, HTML, YAML, Markdown, ZIP, gzip, plain text) are also mapped to their IANA media types.

## API Endpoint

### `GET /runs/{run_id}/ro-crate`

Retrieve the RO-Crate metadata for a completed run.

| Parameter | Default | Response |
|---|---|---|
| `download=false` | JSON-LD | `application/ld+json` |
| `download=true` | ZIP archive | `application/zip` |

When `download=true`, the response is a ZIP archive containing all files referenced in the crate. When `download=false`, only the `ro-crate-metadata.json` content is returned as JSON-LD.

When [authentication](authentication.md) is enabled, this endpoint is protected and requires a valid JWT token.

## Implementation

RO-Crate generation is implemented in `sapporo/ro_crate.py` and called from `run.sh` after the workflow engine completes (or fails). It runs in the same subprocess as the workflow execution.

The entry point is `generate_ro_crate(run_dir)`, invoked from `run.sh` as:

```bash
python3 -c "from sapporo.ro_crate import generate_ro_crate; generate_ro_crate('${run_dir}')"
```

The generation flow:

1. Create a base crate with WRROC profiles and sapporo context.
2. Add the `ComputationalWorkflow` entity from the run request.
3. Add `SoftwareApplication` entities for the workflow engine and sapporo.
4. Build the `CreateAction` with inputs, outputs, logs, and metadata.
5. Run MultiQC and attach statistics.
6. Run samtools/vcftools on applicable output files.
7. Write `ro-crate-metadata.json` and `README.md` to the run directory.

## Validation

The generated RO-Crate metadata can be validated using [roc-validator](https://github.com/ResearchObject/roc-validator):

```bash
uv run roc-validator validate ro-crate-metadata.json
```

All REQUIRED checks from the RO-Crate 1.1 specification should pass. RECOMMENDED checks may produce warnings for optional properties that sapporo does not populate (e.g., `author` on the Root Data Entity, `license` as a `CreativeWork` entity).

## Example

A complete RO-Crate example is available in [`tests/ro-crate/`](../tests/ro-crate/):

- `ro-crate-metadata.json`: Generated metadata (quick reference copy)
- `ro-crate_dir/`: Sample run directory with all source files and generated metadata

See [`tests/ro-crate/README.md`](../tests/ro-crate/README.md) for details.
