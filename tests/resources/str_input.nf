#!/usr/bin/env nextflow
params.str = 'Hello world!'

process step_1 {
    output:
        file 'test_output.txt'

    """
    printf 'Test: ${params.str}' > test_output.txt
    """
}
