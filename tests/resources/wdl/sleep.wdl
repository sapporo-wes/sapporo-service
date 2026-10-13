version 1.0

task sleep {
    command <<< sleep 300 >>>
    runtime {
        docker: "ubuntu:24.04"
    }
}

workflow sleep_workflow {
    call sleep
}
