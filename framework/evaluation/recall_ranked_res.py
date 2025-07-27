# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import re
import json
import pandas as pd
from pathlib import Path
import argparse
from utils import (
    fields_match,
    safe_load_json,
    standardize_chart_info,
    compare_dataframes_em,
    parse_significance_from_dir,
    parse_fields_from_dir
)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ground_truth_dir', required=True)
    parser.add_argument('--final_results_dir', required=True)
    args = parser.parse_args()
    
    GROUND_TRUTH_DIR = Path(args.ground_truth_dir)
    FINAL_RESULTS_DIR = Path(args.final_results_dir)
    
    total_tables_chart_csv = 0
    overall_recalled_chart_csv = 0
    total_chart_tables = 0
    recalled_chart_tables = 0
    total_csv_tables = 0
    recalled_csv_tables = 0
    total_modeling_tables = 0
    recalled_modeling_tables = 0
    total_tables_any = 0
    recalled_tables_any = 0
    
    all_table_dirs = [d for d in GROUND_TRUTH_DIR.iterdir() if d.is_dir()]
    for table_dir in all_table_dirs:
        table_name = table_dir.name
        gt_chart_dir = table_dir / "table_visualization"
        ground_truth_chart_infos = []
        if gt_chart_dir.is_dir():
            gt_chart_files = [f for f in gt_chart_dir.iterdir() if f.is_file() and ('code' in f.name) and f.suffix.lower() == '.json']
            for gt_file in gt_chart_files:
                try:
                    gt_data = json.loads(gt_file.read_text(encoding='utf-8'))
                    code = gt_data.get('code', '')
                    match = re.search(r"#\s*Chart INFO:\s*(\{.*\})", code)
                    if match:
                        chart_info_str = match.group(1).strip()
                        info = safe_load_json(chart_info_str)
                        if info:
                            ground_truth_chart_infos.append(standardize_chart_info(info))
                except:
                    pass
        gt_csv_dir = table_dir / "basic_analysis"
        ground_truth_csv_dfs = []
        if gt_csv_dir.is_dir():
            gt_csv_files = [f for f in gt_csv_dir.iterdir() if f.suffix.lower() == '.csv']
            for gt_file in gt_csv_files:
                try:
                    df = pd.read_csv(gt_file, header=None, low_memory=False)
                    ground_truth_csv_dfs.append(df)
                except:
                    pass
        chart_gt = (len(ground_truth_chart_infos) > 0)
        csv_gt = (len(ground_truth_csv_dfs) > 0)
        
        cand_table_dir = FINAL_RESULTS_DIR / table_name
        if not cand_table_dir.is_dir():
            continue
        
        candidate_chart_infos = []
        code_candidates = [f for f in cand_table_dir.iterdir() if f.suffix.lower() in ('.json', '.jsonl')]
        for code_file in code_candidates:
            try:
                content = code_file.read_text(encoding='utf-8')
                data_json = json.loads(content)
                code_text = data_json.get('code', '')
            except:
                code_text = ""
            match = re.search(r"#\s*Chart INFO:\s*(\{.*\})", code_text)
            if match:
                chart_info_str = match.group(1).strip()
                info = safe_load_json(chart_info_str)
                if info:
                    candidate_chart_infos.append(standardize_chart_info(info))
                    
        candidate_csv_dfs = []
        csv_candidates = [f for f in cand_table_dir.iterdir() if f.suffix.lower() == '.csv']
        for csv_file in csv_candidates:
            try:
                df = pd.read_csv(csv_file, header=None, low_memory=False)
                candidate_csv_dfs.append(df)
            except:
                pass
                
        chart_matched = False
        csv_matched = False
        if chart_gt:
            for c_info in candidate_chart_infos:
                if chart_matched:
                    break
                for gt_info in ground_truth_chart_infos:
                    if (
                        c_info["x_fields"] == gt_info["x_fields"] and
                        fields_match(c_info["y_fields"], gt_info["y_fields"]) and
                        c_info["chart_type"] == gt_info["chart_type"]
                    ):
                        chart_matched = True
                        break
        if csv_gt:
            for cand_df in candidate_csv_dfs:
                if csv_matched:
                    break
                for gt_df in ground_truth_csv_dfs:
                    if compare_dataframes_em(cand_df, gt_df):
                        csv_matched = True
                        break
        if chart_gt:
            total_chart_tables += 1
            if chart_matched:
                recalled_chart_tables += 1
        if csv_gt:
            total_csv_tables += 1
            if csv_matched:
                recalled_csv_tables += 1
        if chart_gt or csv_gt:
            total_tables_chart_csv += 1
            if chart_matched or csv_matched:
                overall_recalled_chart_csv += 1
                
        # 模型任务部分：统一调用 parse_fields_from_dir，不再传递 is_ground_truth 参数
        modeling_dir_gt = table_dir / "stat_modeling"
        fields_dir_gt = table_dir / "modeling_fields"
        gt_significance = parse_significance_from_dir(modeling_dir_gt)
        gt_fields_all = parse_fields_from_dir(fields_dir_gt)
        cand_significance = parse_significance_from_dir(cand_table_dir)
        cand_fields_all = parse_fields_from_dir(cand_table_dir)
        modeling_gt = (len(gt_significance) > 0)
        modeling_matched = False
        if modeling_gt:
            total_modeling_tables += 1
            method_map_gt = {}
            for q_gt, methods_gt in gt_significance.items():
                for m in methods_gt:
                    method_map_gt.setdefault(m, []).append(q_gt)
            for q_cand, methods_cand in cand_significance.items():
                if modeling_matched:
                    break
                if not methods_cand:
                    continue
                fields_cand = cand_fields_all.get(q_cand, set())
                for method_item in methods_cand:
                    candidate_qgts = method_map_gt.get(method_item, [])
                    if not candidate_qgts:
                        continue
                    for q_gt in candidate_qgts:
                        fields_gt = gt_fields_all.get(q_gt, set())
                        if fields_cand and (fields_cand == fields_gt):
                            modeling_matched = True
                            break
                    if modeling_matched:
                        break
            if modeling_matched:
                recalled_modeling_tables += 1
                
        has_any_gt = (chart_gt or csv_gt or (len(gt_significance) > 0))
        matched_any = (chart_matched or csv_matched or modeling_matched)
        if has_any_gt:
            total_tables_any += 1
            if matched_any:
                recalled_tables_any += 1
                
    chart_recall_rate = (recalled_chart_tables / total_chart_tables) if total_chart_tables else 0
    csv_recall_rate = (recalled_csv_tables / total_csv_tables) if total_csv_tables else 0
    chart_csv_recall_rate = (overall_recalled_chart_csv / total_tables_chart_csv) if total_tables_chart_csv else 0
    modeling_recall_rate = (recalled_modeling_tables / total_modeling_tables) if total_modeling_tables else 0
    overall_recall_rate = (recalled_tables_any / total_tables_any) if total_tables_any else 0
    
    print("\n================= Recall Statistics =================")
    print(f"1) Chart: GT tables = {total_chart_tables}, Recalled = {recalled_chart_tables}, Recall = {chart_recall_rate:.2%}")
    print(f"2) CSV:   GT tables = {total_csv_tables}, Recalled = {recalled_csv_tables}, Recall = {csv_recall_rate:.2%}")
    print(f"3) Combined Chart+CSV (only tables with chart or CSV GT): Tables = {total_tables_chart_csv}, Recalled = {overall_recalled_chart_csv}, Recall = {chart_csv_recall_rate:.2%}")
    print(f"4) Modeling: GT tables = {total_modeling_tables}, Recalled = {recalled_modeling_tables}, Recall = {modeling_recall_rate:.2%}")
    print(f"\n*** Overall Recall (Union of Chart/CSV/Modeling tasks) ***")
    print(f"   Total tables with any GT = {total_tables_any}")
    print(f"   Tables recalled in at least one task = {recalled_tables_any}")
    print(f"   Overall Recall = {overall_recall_rate:.2%}\n")

if __name__ == "__main__":
    main()
