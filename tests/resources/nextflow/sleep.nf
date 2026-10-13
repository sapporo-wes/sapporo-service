process SLEEP {
    container 'ubuntu:24.04'

    script:
    "sleep 300"
}

workflow {
    SLEEP()
}
