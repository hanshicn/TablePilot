# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

#!/usr/bin/env bash
export OPENAI_API_KEY="your_API_key"

# gen_explanation.py/gen_basic_analysis.py/gen_table_visualization.py/gen_stat_modeling.py
python gen_explanation.py --input_file "data/txt_table" --output_file "response/table_explanation"

