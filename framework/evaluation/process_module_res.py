# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from pathlib import Path
import shutil
import re
import json
import glob
import argparse

def get_query_number(filename):
    match = re.search(r'query(\d+)', filename)
    return int(match.group(1)) if match else None

def save_query_text(query_text, output_path):
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(query_text)

def get_json_suffix(task_type):
    suffix_map = {
        'basic_analysis': '_rudi.json',
        'table_visualization': '_chart.json',
        'stat_modeling': '_modeling.json'
    }
    return suffix_map.get(task_type, '_rudi.json')

def process_table_results(original_dir, modified_dir, task_type, output_base_dir):
    original_path = Path(original_dir)
    modified_path = Path(modified_dir)
    output_dir = Path(output_base_dir) / task_type
    output_dir.mkdir(parents=True, exist_ok=True)


    table_dirs = {d.name: d for d in modified_path.glob('table_*')}

    missing_queries = {}
    successful_queries = 0
    total_queries = 0

    for table_name, table_dir in table_dirs.items():
        table_output_dir = output_dir / table_name
        table_output_dir.mkdir(exist_ok=True)

        modified_query_nums = set()
        for f in table_dir.glob('query*'):
            if not f.name.endswith('_error.txt'):
                qnum = get_query_number(f.name)
                if qnum is not None:
                    modified_query_nums.add(qnum)
        
        original_table_dir = original_path / table_name
        original_query_nums = set()
        if original_table_dir.exists():
            for f in original_table_dir.glob('query*'):
                if not f.name.endswith('_error.txt'):
                    qnum = get_query_number(f.name)
                    if qnum is not None:
                        original_query_nums.add(qnum)
        
        query_numbers = modified_query_nums.union(original_query_nums)
        if not query_numbers:
            continue

        missing_queries[table_name] = []
        for num in sorted(query_numbers):
            total_queries += 1
            success_files = list(table_dir.glob(f'query{num}*'))
            success_files = [f for f in success_files if not f.name.endswith('_error.txt')]
            if success_files:
                successful_queries += 1
                for src_file in success_files:
                    new_name = f"query{num}_res_opt{src_file.suffix}"
                    shutil.copy2(src_file, table_output_dir / new_name)
            else:
                if original_table_dir.exists():
                    original_files = list(original_table_dir.glob(f'query{num}*'))
                    original_files = [f for f in original_files if not f.name.endswith('_error.txt')]
                    if original_files:
                        successful_queries += 1
                        for src_file in original_files:
                            new_name = f"query{num}_res_org{src_file.suffix}"
                            shutil.copy2(src_file, table_output_dir / new_name)
                    else:
                        missing_queries[table_name].append(num)
                else:
                    missing_queries[table_name].append(num)
    
    print(f"\nStatistics for {task_type} task:")
    total_missing = sum(len(nums) for nums in missing_queries.values())
    for table_name, missing_nums in missing_queries.items():
        if missing_nums:
            print(f"Table {table_name} missing results for queries: {missing_nums}")
    
    answer_rate = successful_queries / total_queries if total_queries > 0 else 0
    print(f"Total queries: {total_queries}")
    print(f"Successful queries: {successful_queries}")
    print(f"Missing queries: {total_missing}")
    print(f"Response rate: {answer_rate:.2%}")

    return missing_queries

def main(args):
    base_path = Path(args.base_path)
    output_base_dir = Path(args.output_base_dir)
    tasks = {
        'basic_analysis': ('basic_analysis_1go', 'basic_analysis_rvd'),
        'table_visualization': ('table_visualization_1go', 'table_visualization_rvd'),
        'stat_modeling': ('stat_modeling_1go', 'stat_modeling_rvd')
    }
    for task_type, (orig_dir, mod_dir) in tasks.items():
        original_dir = base_path / orig_dir
        modified_dir = base_path / mod_dir
        print(f"\nProcessing {task_type} task...")
        process_table_results(original_dir, modified_dir, task_type, output_base_dir)
        print(f"{task_type} task completed")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base_path", required=True, help="Base path for the response directory")
    parser.add_argument("--output_base_dir", required=True, help="Output base directory for combined results")
    args = parser.parse_args()
    main(args)
