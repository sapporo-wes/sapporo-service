cwlVersion: v1.2
class: CommandLineTool
requirements:
  DockerRequirement:
    dockerPull: alpine:3.20
baseCommand: [sleep, "300"]
inputs: []
outputs: []
