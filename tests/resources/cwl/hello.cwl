cwlVersion: v1.2
class: CommandLineTool
baseCommand: [cat]
stdout: output.txt
inputs:
  message_file:
    type: File
    inputBinding:
      position: 1
outputs:
  output_file:
    type: stdout
