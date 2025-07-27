# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

#!/bin/bash

BASE_PATH="/mnt/c/Users/TablePilot_opensource/response"
OUTPUT_BASE_DIR="/mnt/c/Users/TablePilot_opensource/result/combined_results"

python process_queries.py \
    --base_path "$BASE_PATH" \
    --output_base_dir "$OUTPUT_BASE_DIR" \

