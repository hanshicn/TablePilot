# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import json
import shutil
import glob
import re
import argparse

def normalize_query(query):
    q = query.strip()
    if q.startswith('['):
        m = re.search(r'^\[\s*([\'"])(.*?)(\1)', q)
        if m:
            q = m.group(2).strip()
        else:
            if q.endswith(']'):
                q = q[1:-1].strip()
            else:
                q = re.sub(r'^\[[^\]]+\]\s*', '', q)
    q = re.sub(r',\s*(\.\.\.)?$', '', q).strip()
    return q

def compute_score(query_item):
    c = query_item["criteria"]
    return (c["Meaningful"]["score"] +
            c["Relative"]["score"] +
            c["Reasonableness"]["score"] +
            c["Diversity"]["score"] +
            c["Interpretable"]["score"] +
            c["Insightful"]["score"])

def get_sorted_queries(queries):
    scored_list = []
    for idx, q_item in enumerate(queries):
        total_score = compute_score(q_item)
        scored_list.append((q_item["query"], idx + 1, total_score))
    scored_list_sorted = sorted(scored_list, key=lambda x: (-x[2], x[1]))
    return scored_list_sorted

def rename_and_copy_files(folder_to_search, query_text, new_prefix, table_output_dir):
    pattern_txt = os.path.join(folder_to_search, "query*.txt")
    candidates = glob.glob(pattern_txt)
    candidates = [f for f in candidates if "res" not in os.path.basename(f)]
    for fpath in candidates:
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if normalize_query(content) == normalize_query(query_text):
            fname = os.path.basename(fpath)
            m = re.match(r"^query(\d+)(.*)\.txt$", fname)
            if not m:
                continue
            old_number = m.group(1)
            prefix_pattern = os.path.join(folder_to_search, f"query{old_number}*")
            matched_files = glob.glob(prefix_pattern)
            for src_file in matched_files:
                base_src_name = os.path.basename(src_file)
                new_name = re.sub(r"^query" + re.escape(old_number), new_prefix, base_src_name)
                dst_file = os.path.join(table_output_dir, new_name)
                shutil.copy(src_file, dst_file)
            return True
    return False

def main(args):
    for file_name in os.listdir(args.ranking_dir):
        if not file_name.endswith("_ranked.json"):
            continue
        table_prefix = file_name[:-len("_ranked.json")]
        if table_prefix.startswith("table_"):
            table_name = table_prefix[len("table_"):]
        else:
            table_name = table_prefix
        json_path = os.path.join(args.ranking_dir, file_name)
        with open(json_path, "r", encoding="utf-8") as jf:
            queries = json.load(jf)
        sorted_queries = get_sorted_queries(queries)
        table_output_dir = os.path.join(args.final_dir, "table_" + table_name)
        os.makedirs(table_output_dir, exist_ok=True)
        subdirs = ["basic_analysis", "table_visualization", "stat_modeling"]
        match_count = 0
        for q_text, original_idx, score in sorted_queries:
            if match_count >= args.result_count:
                break
            match_found = False
            for sub in subdirs:
                table_dir = os.path.join(args.combined_dir, sub, "table_" + table_name)
                if os.path.isdir(table_dir):
                    result = rename_and_copy_files(
                        folder_to_search=table_dir,
                        query_text=q_text,
                        new_prefix=f"query{match_count+1}",
                        table_output_dir=table_output_dir
                    )
                    if result:
                        match_found = True
            if match_found:
                match_count += 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ranking_dir", required=True)
    parser.add_argument("--combined_dir", required=True)
    parser.add_argument("--final_dir", required=True)
    parser.add_argument("--result_count", type=int, default=5)
    args = parser.parse_args()
    main(args)
