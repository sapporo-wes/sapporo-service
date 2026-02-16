params.input_file = 'input.txt'
params.outdir = './results'

process HELLO {
    publishDir params.outdir, mode: 'copy'

    input:
    path input_file

    output:
    path 'output.txt'

    script:
    "cat ${input_file} > output.txt"
}

workflow {
    input_ch = Channel.fromPath(params.input_file, checkIfExists: true)
    HELLO(input_ch)
}
