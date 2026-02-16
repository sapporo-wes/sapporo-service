version 1.0

task hello {
    input {
        File input_file
    }
    command <<< cat ~{input_file} > output.txt >>>
    output {
        File output_file = "output.txt"
    }
    runtime {
        docker: "ubuntu:24.04"
    }
}

workflow hello_workflow {
    input {
        File input_file
    }
    call hello {
        input: input_file = input_file
    }
    output {
        File final_output = hello.output_file
    }
}
