# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

#!/bin/bash

# please concat the path with ";"
INPUT_FOLDERS="response/basic_analysis;response/table_visualization;response/stat_modeling"

python revision.py --input_folders "$INPUT_FOLDERS"
