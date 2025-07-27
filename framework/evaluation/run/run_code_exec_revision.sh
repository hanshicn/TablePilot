# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

#!/bin/bash
# Please execute three task individually

python code_exec_revision.py \
  --exec_dir "response/basic_analysis_revised" \
  --csv_dir "data/csv_table" \
  --table_format_dir "data/txt_table" \
  --output_base_dir "result/basic_anlaysis_rvd"
