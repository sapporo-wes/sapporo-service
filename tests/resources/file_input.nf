#!/usr/bin/env nextflow
params.input_file = './nf_test_input.txt'
ch = Channel.fromPath(params.input_file, checkIfExists:true)

process step_1 {
    input:
        file input_file from ch

    output:
        file 'test_output.txt'

    """
    printf Test: >> test_output.txt
    cat ${input_file} >> test_output.txt
    """
}
