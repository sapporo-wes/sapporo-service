#!/usr/bin/env nextflow
params.str = 'Hello world!'
params.outdir = './test_output'

process step_1 {
    publishDir params.outdir, mode: 'copy'

    output:
        file 'test_output.txt'

    """
    printf 'Test: ${params.str}' > test_output.txt
    """
}
