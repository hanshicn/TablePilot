# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
import pandas as pd
from pathlib import Path
import sys
import traceback
from io import StringIO
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import concurrent.futures
import warnings
import io
import re
import argparse

def execute_code_with_timeout(code, local_namespace, timeout=120):
    def run():
        exec(code, local_namespace, local_namespace)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run)
        try:
            future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            executor._threads.clear()
            concurrent.futures.thread._threads_queues.clear()
            raise TimeoutError(f"Execution exceeded timeout of {timeout} seconds")
        except Exception as e:
            executor._threads.clear()
            concurrent.futures.thread._threads_queues.clear()
            raise e

class WarningCatcher:
    def __init__(self):
        self.warnings = io.StringIO()
    def __call__(self, message, category, filename, lineno, file=None, line=None):
        self.warnings.write(f"Warning: {category.__name__}: {message}\n")

def main(args):
    exec_dir = Path(args.exec_dir)
    csv_dir = Path(args.csv_dir)
    table_format_dir = Path(args.table_format_dir)
    output_base_dir = Path(args.output_base_dir)
    output_base_dir.mkdir(parents=True, exist_ok=True)
    existing_tables = {d.name for d in output_base_dir.iterdir() if d.is_dir()}
    total_queries = 0
    successful_queries = 0
    for table_dir in exec_dir.glob('table_*'):
        table_name = table_dir.name
        if table_name in existing_tables:
            continue
        print(f"Processing table {table_name}")
        data_file_csv = csv_dir / f"{table_name}.csv"
        data_file_csv = str(data_file_csv).replace('\\', '/')
        output_dir = output_base_dir / f"{table_name}"
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            for query_file in table_dir.glob('query*.json'):
                total_queries += 1
                try:
                    with open(query_file, 'r', encoding='utf-8') as f:
                        query_data = json.load(f)
                    code = query_data.get('optimized_code', '')
                    if not code:
                        print(f"No code found in {query_file}, skipping")
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
                    query_number = query_file.stem.replace('query', '').replace('_error', '')
                    output_filename = f"query{query_number}"
                    try:
                        warning_catcher = WarningCatcher()
                        warnings.showwarning = warning_catcher
                        local_namespace = {}
                        pattern = r"'[^']*output[^']*\.csv'"
                        if re.search(pattern, code_modified):
                            csv_filepath = output_dir / f"{output_filename}.csv"
                            replacement_path = csv_filepath.as_posix()
                            code_modified = re.sub(pattern, f"r'{replacement_path}'", code_modified)
                            execute_code_with_timeout(code_modified, local_namespace)
                            print(f"csv saved: {csv_filepath}")
                        elif 'plt.show()' in code_modified:
                            image_filepath = output_dir / f"{output_filename}.png"
                            code_modified = code_modified.replace(
                                'plt.show()',
                                f"plt.savefig(r'{str(image_filepath)}')\nplt.close()"
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
                        warnings_text = warning_catcher.warnings.getvalue()
                        if warnings_text:
                            print(f"Warnings occurred while processing {query_file.name}")
                        successful_queries += 1
                    except TimeoutError as e:
                        print(f"Timeout occurred while processing {query_file.name}")
                        error_filename = output_dir / f"query{query_number}_error.txt"
                        table_format2_file = table_format_dir / f"{table_name}.txt"
                        if table_format2_file.exists():
                            with open(table_format2_file, 'r', encoding='utf-8') as tf:
                                table_content = tf.read()
                        else:
                            table_content = f"Table file {table_format2_file} does not exist."
                        with open(error_filename, 'w', encoding='utf-8') as error_file:
                            error_file.write(f"Table Name: {table_name}\n")
                            error_file.write(f"{table_content}\n\n")
                            error_file.write(f"Query Number: {query_number}\n")
                            error_file.write(f"Query: {query_data.get('query', 'N/A')}\n\n")
                            error_file.write(f"Code:\n{code}\n\n")
                            error_file.write(f"Error Message:\nTimeout Error: Execution exceeded timeout of 120 seconds\n")
                            if warning_catcher.warnings.getvalue():
                                error_file.write(f"\nWarnings:\n{warning_catcher.warnings.getvalue()}")
                        print(f"Timeout error details saved to {error_filename}")
                    except Exception as e:
                        print(f"Error occurred while processing {query_file.name}")
                        error_filename = output_dir / f"query{query_number}_error.txt"
                        table_format2_file = table_format_dir / f"{table_name}.txt"
                        if table_format2_file.exists():
                            with open(table_format2_file, 'r', encoding='utf-8') as tf:
                                table_content = tf.read()
                        else:
                            table_content = f"Table file {table_format2_file} does not exist."
                        with open(error_filename, 'w', encoding='utf-8') as error_file:
                            error_file.write(f"Table Name: {table_name}\n")
                            error_file.write(f"{table_content}\n\n")
                            error_file.write(f"Query Number: {query_number}\n")
                            error_file.write(f"Query: {query_data.get('query', 'N/A')}\n\n")
                            error_file.write(f"Code:\n{code}\n\n")
                            error_file.write(f"Error Message:\n{traceback.format_exc()}\n")
                            if warning_catcher.warnings.getvalue():
                                error_file.write(f"\nWarnings:\n{warning_catcher.warnings.getvalue()}")
                        print(f"Error details saved to {error_filename}")
                except Exception as e:
                    print(f"Error processing file {query_file.name}: {str(e)}")
                    continue
        except Exception as e:
            print(f"Error processing table directory {table_dir}: {str(e)}")
            continue
    plt.close('all')
    print(f"\nFinal Execution Statistics:")
    print(f"Total queries processed: {total_queries}")
    print(f"Successful queries: {successful_queries}")
    print(f"Failed queries: {total_queries - successful_queries}")
    if total_queries > 0:
        print(f"Success rate: {(successful_queries/total_queries*100):.2f}%")
    else:
        print("Success rate: N/A (no queries processed)")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--exec_dir', required=True)
    parser.add_argument('--csv_dir', required=True)
    parser.add_argument('--table_format_dir')
    parser.add_argument('--output_base_dir')
    args = parser.parse_args()
    main(args)
