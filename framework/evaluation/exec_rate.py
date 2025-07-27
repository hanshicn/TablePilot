# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import glob
import argparse

def count_errors_in_folder(base_path):
    table_folders = glob.glob(os.path.join(base_path, "table_*"))
    total_files = 0
    error_files = 0
    for folder in table_folders:
        files = os.listdir(folder)
        total_files += len(files)
        error_count = sum(1 for f in files if 'error' in f.lower())
        error_files += error_count
    return total_files, error_files

def calculate_success_rate(total, errors):
    if total == 0:
        return 0
    return (total - errors) / total * 100

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--path1', required=True, help='Path for the first directory')
    parser.add_argument('--path2', required=True, help='Path for the second directory')
    args = parser.parse_args()
    path1 = args.path1
    path2 = args.path2
    total1, errors1 = count_errors_in_folder(path1)
    success_rate1 = calculate_success_rate(total1, errors1)
    print(f"Folder 1 Statistics:")
    print(f"Total files: {total1}")
    print(f"Successful files: {total1 - errors1}")
    print(f"Success rate: {success_rate1:.2f}%\n")
    table_folders1 = glob.glob(os.path.join(path1, "table_*"))
    table_folders2 = glob.glob(os.path.join(path2, "table_*"))
    query_errors = {}
    for folder in table_folders1:
        folder_name = os.path.basename(folder)
        files = os.listdir(folder)
        for f in files:
            query_name = f.split('_')[0]
            if 'error' in f.lower():
                query_errors[f"{folder_name}_{query_name}"] = True
    both_error = 0
    for folder in table_folders2:
        folder_name = os.path.basename(folder)
        files = os.listdir(folder)
        for f in files:
            query_name = f.split('_')[0]
            key = f"{folder_name}_{query_name}"
            if 'error' in f.lower() and key in query_errors:
                both_error += 1
    combined_success_rate = calculate_success_rate(total1, both_error)
    print(f"Combined Statistics:")
    print(f"Total queries: {total1}")
    print(f"Total successful queries: {total1 - both_error}")
    print(f"Success rate: {combined_success_rate:.2f}%")

if __name__ == "__main__":
    main()
