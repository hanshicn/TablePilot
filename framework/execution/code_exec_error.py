# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
from pathlib import Path
import sys
import traceback
import matplotlib
matplotlib.use('Agg')
from io import StringIO
import concurrent.futures
import re
import argparse

def execute_code_with_timeout(code, local_namespace, timeout=120):
    def run():
        exec(code, local_namespace, local_namespace)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future = executor.submit(run)
        try:
            future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            raise TimeoutError(f"Execution exceeded timeout of {timeout} seconds.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exec_dir", required=True)
    parser.add_argument("--csv_dir", required=True)
    parser.add_argument("--table_txt_dir", required=True)
    parser.add_argument("--output_base_dir", required=True)
    args = parser.parse_args()

    exec_dir = Path(args.exec_dir)
    csv_dir = Path(args.csv_dir)
    table_format3_dir = Path(args.table_txt_dir)
    output_base_dir = Path(args.output_base_dir)
    output_base_dir.mkdir(parents=True, exist_ok=True)

    existing_tables = {d.name for d in output_base_dir.iterdir() if d.is_dir()}
    print(f"Processed tables: {len(existing_tables)}")
    total_queries = 0
    successful_queries = 0

    for qc_file in exec_dir.glob('table_*_modeling.json'):
        table_name = qc_file.stem.replace('_modeling', '')
        if table_name in existing_tables:
            continue
        print(f"Processing file {qc_file}")
        with open(qc_file, 'r', encoding='utf-8') as f:
            recommendations = json.load(f)
        output_dir = output_base_dir / table_name
        output_dir.mkdir(parents=True, exist_ok=True)
        data_file_csv = csv_dir / f"{table_name}.csv"
        data_file_csv = str(data_file_csv).replace('\\', '/')
        for idx, recommendation in enumerate(recommendations):
            total_queries += 1
            code = recommendation.get('code', '')
            if not code:
                print(f"No code found in recommendation {idx + 1}. Skipping.")
                continue
            code_modified = code.replace(
                "pd.read_csv('table_name.csv')",
                f"pd.read_csv(r'{data_file_csv}')"
            ).replace(
                'pd.read_csv("table_name.csv")',
                f"pd.read_csv(r'{data_file_csv}')"
            ).replace(
                "file = 'table_name.csv'",
                f"file = r'{data_file_csv}'"
            ).replace(
                'file = "table_name.csv"',
                f'file = r"{data_file_csv}"'
            ).replace("sep='\\t'", "sep='\t'")
            code_modified = re.sub(r"pd\.read_csv\('table_\d+\.csv'\)", f"pd.read_csv(r'{data_file_csv}')", code_modified)
            query_number = idx + 1
            output_filename = f"query{query_number}"
            try:
                local_namespace = {}
                pattern = r"'[^']*output[^']*\.csv'"
                if re.search(pattern, code_modified):
                    csv_filepath = output_dir / f"query{idx + 1}.csv"
                    replacement_path = csv_filepath.as_posix()
                    code_modified = re.sub(pattern, f"r'{replacement_path}'", code_modified)
                    execute_code_with_timeout(code_modified, local_namespace)
                    print(f"CSV saved: {csv_filepath}")
                elif 'plt.show()' in code_modified:
                    image_filepath = output_dir / f"{output_filename}.png"
                    code_modified = code_modified.replace(
                        'plt.show()',
                        f"plt.savefig(r'{str(image_filepath)}')"
                    )
                    execute_code_with_timeout(code_modified, local_namespace)
                    print(f"Image saved: {image_filepath}")
                else:
                    old_stdout = sys.stdout
                    sys.stdout = mystdout = StringIO()
                    execute_code_with_timeout(code_modified, local_namespace)
                    sys.stdout = old_stdout
                    execution_output = mystdout.getvalue()
                    output_filepath = output_dir / f"{output_filename}.txt"
                    with open(output_filepath, 'w', encoding='utf-8') as f_out:
                        f_out.write(execution_output)
                    print(f"Output saved: {output_filepath}")
                successful_queries += 1
            except TimeoutError as e:
                print(f"Timeout occurred while processing table '{table_name}' query {query_number}: {e}")
                error_filename = output_dir / f"query{query_number}_error.txt"
                table_format2_file = table_format3_dir / f"{table_name}.txt"
                if table_format2_file.exists():
                    with open(table_format2_file, 'r', encoding='utf-8') as tf:
                        table_content = tf.read()
                else:
                    table_content = f"Table file {table_format2_file} does not exist."
                with open(error_filename, 'w', encoding='utf-8') as error_file:
                    error_file.write(f"Table Name: {table_name}\n")
                    error_file.write(f"{table_content}\n\n")
                    error_file.write(f"Query Number: {query_number}\n")
                    error_file.write(f"Query: {recommendation.get('query', 'N/A')}\n\n")
                    error_file.write(f"Code:\n{code}\n\n")
                    error_file.write(f"Error Message:\n{str(e)}\n\n")
                print(f"Timeout error details saved to {error_filename}")
            except Exception as e:
                print(f"Error occurred while processing table '{table_name}' query {query_number}:")
                traceback.print_exc()
                error_filename = output_dir / f"query{query_number}_error.txt"
                table_format2_file = table_format3_dir / f"{table_name}.txt"
                if table_format2_file.exists():
                    with open(table_format2_file, 'r', encoding='utf-8') as tf:
                        table_content = tf.read()
                else:
                    table_content = f"Table file {table_format2_file} does not exist."
                with open(error_filename, 'w', encoding='utf-8') as error_file:
                    error_file.write(f"Table Name: {table_name}\n")
                    error_file.write(f"{table_content}\n\n")
                    error_file.write(f"Query Number: {query_number}\n")
                    error_file.write(f"Query: {recommendation.get('query', 'N/A')}\n\n")
                    error_file.write(f"Code:\n{code}\n\n")
                    error_file.write(f"Error Message:\n{traceback.format_exc()}\n\n")
                print(f"Error details saved to {error_filename}")
    print(f"\nExecution completed.")
    print(f"Total queries processed: {total_queries}")
    print(f"Successful queries: {successful_queries}")
    print(f"Failed queries: {total_queries - successful_queries}")

if __name__ == "__main__":
    main()
