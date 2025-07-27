# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

#!/bin/bash

RANKING_DIR="/mnt/c/Users/TablePilot_opensource/response/ranking"
COMBINED_DIR="/mnt/c/Users/TablePilot_opensource/result/combined_results"
FINAL_DIR="/mnt/c/Users/TablePilot_opensource/result/final_results_test"
RESULT_COUNT=5

python3 sum_ranking_res.py \
    --ranking_dir "$RANKING_DIR" \
    --combined_dir "$COMBINED_DIR" \
    --final_dir "$FINAL_DIR" \
    --result_count "$RESULT_COUNT"
