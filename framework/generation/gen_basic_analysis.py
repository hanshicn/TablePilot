# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
from pathlib import Path
import argparse
from openai import OpenAI
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
import os

API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    raise ValueError("Please set the OPENAI_API_KEY environment variable.")

def get_rudi_prompt(table_prompt: str, table_exp: str):
    formatted_demo = json.dumps(table_exp)
    return f"""
    Please propose some queries along with the corresponding executable code for the following table: \n{table_prompt}\n
    The table explanation is provided below to guide your query and code generation:
    ```json
    {formatted_demo}
    ```
    Generate up to five queries with their corresponding code, formatted as JSON.
    """

response_format={
    "type": "json_schema",
    "json_schema": {
        "name": "basic_analysis_schema",
        "schema": {
            "type": "object",  
            "properties": {
                "results": {  
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "code": {"type": "string"}
                        },
                        "required": ["query", "code"],
                        "additionalProperties": False
                    }
                }
            },
            "required": ["results"],
            "additionalProperties": False
        }
    }
}

def process_file(filename: Path, system_prompt: str, output_folder: Path):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            table_prompt = f.read()
        
        json_path = output_folder / f"{filename.stem}_explanations.json"
        table_exp = json.load(open(json_path, "r", encoding="utf-8")) if json_path.exists() else "No explanation available."
        
        user_prompt = get_rudi_prompt(table_prompt, table_exp)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        
        client = OpenAI(api_key=API_KEY)
        completion = client.chat.completions.create(
            model="gpt-4o",  
            messages=messages,
            response_format=response_format,
            tokens=8000,
            temperature=0,
        )
        
        result = completion.choices[0].message.content
        try:
            explanation = json.loads(result)
        except Exception:
            explanation = {"result": result}
        
        output_path = output_folder / (filename.stem + "_rudi.json")
        with open(output_path, "w", encoding="utf-8") as out_file:
            json.dump(explanation, out_file, ensure_ascii=False, indent=2)
        
    except Exception as e:
        print(f"Error processing file {filename.name}: {str(e)}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_table_folder", required=True)
    parser.add_argument("--output_file", required=True)
    args = parser.parse_args()

    input_folder = Path(args.input_table_folder)
    output_folder = Path(args.output_file)
    output_folder.mkdir(exist_ok=True, parents=True)
    
    system_prompt_path = Path("prompt/system/rudimentary.md")
    system_prompt = system_prompt_path.read_text(encoding="utf-8") if system_prompt_path.exists() else ""
    
    filenames = [
        filename for filename in input_folder.iterdir()
        if filename.suffix == ".txt" and "table" in filename.stem
    ]
    
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(process_file, filename, system_prompt, output_folder): filename for filename in filenames}
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures)):
            future.result()

if __name__ == "__main__":
    main()
