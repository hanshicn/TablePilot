# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import re
import ast
import json
import pandas as pd
from pathlib import Path

def normalize_string(s):
    return re.sub(r"\W", "", str(s)).lower()

def fields_match(list1, list2):
    if len(list1) != len(list2):
        return False
    for a, b in zip(list1, list2):
        if normalize_string(a) != normalize_string(b):
            return False
    return True

def safe_load_json(content):
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        try:
            data = ast.literal_eval(content)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return None

def standardize_chart_info(info):
    return {
        "x_fields": normalize_string(info.get('x_fields', '')),
        "y_fields": [normalize_string(y) for y in info.get('y_fields', [])],
        "chart_type": normalize_string(info.get('chart_type', ''))
    }

def compare_dataframes_em(df1, df2):
    if len(df1) != len(df2):
        return False
    values1 = df1.iloc[1:].values.tolist()
    values2 = df2.iloc[1:].values.tolist()
    return values1 == values2

def check_mape(content: str) -> bool:
    match = re.search(r'MAPE:\s*(\d+\.\d+)', content)
    if match:
        try:
            return float(match.group(1)) <= 1.0
        except:
            return False
    return False

def check_pearson(content: str) -> bool:
    if re.search(r'Correlation Method:\s*Pearson', content):
        p_match = re.search(r'P-value:\s*(\d+\.\d+(?:e[+-]\d+)?)', content)
        if p_match:
            try:
                return float(p_match.group(1)) < 0.05
            except:
                return False
    return False

def check_rsquared(content: str) -> bool:
    if "OLS Regression Results" in content:
        r_match = re.search(r'R-squared:\s*(\d+\.\d+)', content)
        if r_match:
            try:
                return float(r_match.group(1)) > 0.9
            except:
                return False
    return False

def get_significance_methods(content: str) -> set:
    methods = set()
    if check_mape(content):
        methods.add("mape")
    if check_pearson(content):
        methods.add("pearson")
    if check_rsquared(content):
        methods.add("rsquared")
    return methods

def parse_query_number(filename: str) -> str:
    match = re.search(r'query(\d+)', filename)
    return match.group(1) if match else ""

def parse_significance_from_dir(directory: Path) -> dict:
    sig_dict = {}
    if not directory.is_dir():
        return sig_dict
    for res_file in directory.glob("query*res*.txt"):
        q_num = parse_query_number(res_file.name)
        try:
            content = res_file.read_text(encoding='utf-8')
        except:
            content = ""
        methods = get_significance_methods(content)
        if methods:
            sig_dict[q_num] = methods
    return sig_dict

def parse_fields_from_dir(directory: Path) -> dict:
    fields_dict = {}
    if not directory.is_dir():
        return fields_dict
    for f_path in directory.glob("query*_fields.json"):
        q_num = parse_query_number(f_path.name)
        try:
            data = json.loads(f_path.read_text(encoding='utf-8'))
            f_list = data.get("fields", [])
            fields_dict[q_num] = set(f_list)
        except:
            fields_dict[q_num] = set()
    for f_path in directory.glob("query*_code.jsonl"):
        q_num = parse_query_number(f_path.name)
        try:
            data = json.loads(f_path.read_text(encoding='utf-8'))
            code_text = data.get("code", "")
        except:
            code_text = ""
        bracket_contents = re.findall(r"\[\s*([^\]]+)\s*\]", code_text)
        extracted_columns = []
        for content in bracket_contents:
            cols = re.findall(r"['\"]([^'\"]+)['\"]", content)
            extracted_columns.extend(cols)
        unique_extracted_columns = {col.strip() for col in extracted_columns if col.strip()}
        fields_dict[q_num] = unique_extracted_columns
    return fields_dict
