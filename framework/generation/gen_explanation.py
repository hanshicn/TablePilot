# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

#!/usr/bin/env python3
import json
import argparse
from pathlib import Path
import os
import concurrent.futures
from tqdm import tqdm
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor

API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    raise ValueError("Please set the OPENAI_API_KEY environment variable.")

def get_user_prompt(table: str):
    return f"Please propose explanations for the following table:\n{table}"

response_format = {
    "type": "json_schema",
    "json_schema": {
        "name": "table_analysis_schema",
        "schema": {
            "type": "object",
            "properties": {
                "Table Theme": {
                    "type": "string",
                    "description": "A brief description of the table's main theme and purpose"
                },
                "Columns": {
                    "type": "object",
                    "description": "Detailed descriptions of each column in the table",
                    "additionalProperties": {
                        "type": "string",
                        "description": "Description of what the column represents and its significance"
                    }
                },
                "Column Relationships": {
                    "type": "object",
                    "description": "Explanations of how different columns relate to and interact with each other",
                    "additionalProperties": {
                        "type": "string",
                        "description": "Description of how this column relates to other columns"
                    }
                }
            },
            "required": ["Table Theme", "Columns", "Column Relationships"],
            "additionalProperties": False
        }
    }
}

def process_file(filename: Path, system_prompt: str, output_folder: Path):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            table_content = f.read()
    except Exception as e:
        print(f"Error reading file {filename.name}: {e}")
        return

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": get_user_prompt(table_content)}
    ]
    
    try:
        client = OpenAI(api_key=API_KEY)
        completion = client.chat.completions.create(
            model="gpt-4o",  
            messages=messages,
            response_format=response_format,
            temperature=0,
            max_tokens=8000
        )
    except Exception as e:
        print(f"Error calling API for {filename.name}: {e}")
        return

    result = completion.choices[0].message.content
    try:
        explanation = json.loads(result)
    except Exception:
        explanation = {"result": result}

    output_path = output_folder / (filename.stem + "_explanation.json")
    try:
        with open(output_path, "w", encoding="utf-8") as out_file:
            json.dump(explanation, out_file, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error writing output for {filename.name}: {e}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_table_folder", required=True)
    parser.add_argument("--output_file", required=True)
    args = parser.parse_args()

    input_folder = Path(args.input_table_folder)
    output_folder = Path(args.output_file)
    output_folder.mkdir(exist_ok=True, parents=True)

    system_prompt_path = Path("prompt/system/explanation.md")
    if system_prompt_path.exists():
        with open(system_prompt_path, "r", encoding="utf-8") as f:
            system_prompt = f.read()
    else:
        system_prompt = ""

    filenames = [
        f for f in input_folder.iterdir()
        if f.is_file() and f.suffix == ".txt" and "table" in f.stem
    ]

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(process_file, filename, system_prompt, output_folder): filename for filename in filenames}
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures)):
            future.result()

if __name__ == "__main__":
    main()
