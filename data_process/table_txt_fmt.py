# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import argparse
import pandas as pd
from pathlib import Path
import string

def generate_column_labels(num_columns):
    letters = string.ascii_uppercase
    labels = []
    for i in range(num_columns):
        if i < 26:
            labels.append(letters[i])
        else:
            first_letter = letters[(i // 26) - 1]
            second_letter = letters[i % 26]
            labels.append(first_letter + second_letter)
    return labels

def is_numeric(series):
    return pd.api.types.is_numeric_dtype(series)

def process_file(input_file, output_file):
    df = pd.read_csv(input_file)
    column_labels = generate_column_labels(len(df.columns))
    output_lines = ["Table:"]
    for i, col in enumerate(df.columns):
        label = column_labels[i]
        numeric = is_numeric(df[col])
        non_na_values = df[col].dropna()
        sampled_values = non_na_values.sample(n=min(5, len(non_na_values))).sort_index().tolist()
        col_type = ", Numeric" if numeric else ""
        if numeric:
            formatted_values = ", ".join(str(value) for value in sampled_values)
        else:
            formatted_values = "', '".join(str(value) for value in sampled_values)
            formatted_values = f"'{formatted_values}'"
        if len(non_na_values) > 5:
            output_lines.append(f"- '{col}' (Column {label}{col_type}): [{formatted_values}, ... ]")
        else:
            output_lines.append(f"- '{col}' (Column {label}{col_type}): [{formatted_values}]")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(output_lines))
    print(f"Successfully processed {output_file}")

def main(input_path, output_path):
    input_path = Path(input_path)
    output_path = Path(output_path)
    
    # If input is a directory, process all CSV files within it.
    if input_path.is_dir():
        output_path.mkdir(parents=True, exist_ok=True)
        for csv_file in input_path.glob('*.csv'):
            out_file = output_path / f"{csv_file.stem}.txt"
            try:
                process_file(csv_file, out_file)
            except Exception as e:
                print(f"Error processing {csv_file}: {e}")
    else:
        # Assume input is a file; ensure the output directory exists.
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            process_file(input_path, output_path)
        except Exception as e:
            print(f"Error processing {input_path}: {e}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Process CSV files to generate formatted txt table output.'
    )
    parser.add_argument('--input_file', type=str, required=True, help='Input table CSV files')
    parser.add_argument('--output_file', type=str, required=True, help='Output table txt files')
    args = parser.parse_args()
    main(args.input_file, args.output_file)
