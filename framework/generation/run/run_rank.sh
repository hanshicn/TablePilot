# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

#!/bin/bash

INPUT_FOLDER="result/combined_results"
OUTPUT_FOLDER="response/ranking"

# 执行 Python 脚本
python rank.py --input_folder "$INPUT_FOLDER" --output_folder "$OUTPUT_FOLDER"