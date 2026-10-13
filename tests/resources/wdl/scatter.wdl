version 1.0

task write_one {
    input {
        Int i
    }
    command <<< echo ~{i} > out_~{i}.txt >>>
    output {
        File out = "out_~{i}.txt"
    }
    runtime {
        docker: "ubuntu:24.04"
    }
}

workflow scatter_workflow {
    input {
        Array[Int] indexes
    }
    scatter (i in indexes) {
        call write_one {
            input: i = i
        }
    }
    output {
        Array[File] outs = write_one.out
    }
}
