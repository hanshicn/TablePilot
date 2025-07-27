# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import base64
import json
import os
import argparse
from openai import OpenAI
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures
import sys

API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    raise ValueError("Please set the OPENAI_API_KEY environment variable.")

def read_system_prompt():
    system_prompt_path = "prompt/system/revision.md"
    with open(system_prompt_path, 'r') as file:
        return file.read()


def get_user_prompt(table_name: str, execution_result: str, base_path: str):
    qc_path = base_path  # Set qc_path to current input folder
    table_info_path = "our_dataset/test_table_txt"
    
    table_info_file = os.path.join(table_info_path, f"{table_name}.txt")
    with open(table_info_file, 'r', encoding='utf-8') as file:
        table_info = file.read()
    
    user_prompt = ""
    user_prompt_add = """
    Refine the code as needed, ensuring consistency in the analysis type. If there is room for improvement, start by describing your direction and reasoning for the optimization, then provide the optimized code.
    When verifying the code, please refrain from altering the original table's file name or reading method, as shown below:
    ```python
    import pandas as pd
    df = pd.read_csv('table_name.csv')
    ```
    The output format and content of the optimized code should remain consistent with the original code, without generating intermediate results or additional outputs.
    Avoid changing the file name and format used for outputting or displaying the execution results. Please focus solely on making accurate verifications to the data analysis logic within the code, without altering how the input is read or the output is saved. 
    """
    
    if "query" in execution_result and "error" not in execution_result:
        query_num = int("".join(filter(str.isdigit, execution_result)))
        
        with open(os.path.join(qc_path, f"{table_name}_modeling.json"), 'r', encoding='utf-8') as json_file:
            queries_code = json.load(json_file)
        
        execution_result_path = os.path.join(base_path, table_name, execution_result)
        if execution_result.lower().endswith('.png'):
            execution_section = "The execution result is an image file."
        else:
            with open(execution_result_path, 'r', encoding='utf-8', errors='ignore') as file:
                execution_content = file.read()
            execution_section = execution_content if len(execution_content) <= 1000 else "Execution result is too long to display."
        
        if query_num <= len(queries_code):
            query_code_pair = queries_code[query_num - 1]
            user_prompt = f"""Please review and optimize the following content according to the guidelines:
### Table Information:
```
{table_info}
```
### Query Details:
**Query**: {query_code_pair['query']}
**Code**:
```python
{query_code_pair['code']}
```
### Execution Result:
```
{execution_section}
```""" + user_prompt_add + """\nPlease ensure that the optimized code can produce the correct results; otherwise, do not proceed with the optimization."""
    
    elif "error" in execution_result:
        error_file_path = os.path.join(base_path, table_name, execution_result)
        with open(error_file_path, 'r') as file:
            error_content = file.read()
        
        user_prompt = f"""The current code matched to the query is incorrect. Please analyze the reasons for the error and suggest how it can be improved. Please review and correct the following content according to the guidelines:
### Error Content:
```
{error_content}
```
""" + user_prompt_add + """\nPlease ensure that the optimized code can produce the correct results."""
    
    return user_prompt

def encode_image(image_path):
    with open(image_path, 'rb') as image_file:
        return base64.b64encode(image_file.read()).decode('ascii')

def create_messages(system_prompt: str, user_prompt: str, image_path: str = None):
    messages = [
        {
            "role": "system",
            "content": [
                {
                    "type": "text",
                    "text": system_prompt
                }
            ]
        }
    ]
    
    user_content = [{"type": "text", "text": user_prompt}]
    
    # if image exists, add image content
    if image_path and os.path.exists(image_path):
        encoded_image = encode_image(image_path)
        user_content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{encoded_image}"
            }
        })
    
    messages.append({
        "role": "user",
        "content": user_content
    })
    
    return messages

def worker(table_name, execution_result, system_prompt, base_path, output_dir):
    try:
        execution_result_path = os.path.join(base_path, table_name, execution_result)
        image_path = None
        if execution_result.lower().endswith('.png'):
            image_path = execution_result_path
            
        user_prompt = get_user_prompt(table_name, execution_result, base_path)
        messages = create_messages(system_prompt, user_prompt, image_path)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        
        client = OpenAI(api_key=API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=3000,
            temperature=0,
        )
        
        content = json.loads(response.choices[0].message.content)
        table_folder = os.path.join(output_dir, table_name)
        os.makedirs(table_folder, exist_ok=True)
        
        output_filename = execution_result.replace('.csv', '').replace('.txt', '').replace('.png', '') + '.json'
        output_path = os.path.join(table_folder, output_filename)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(content, f, indent=4, ensure_ascii=False)
        
        return True
    except Exception as e:
        print(f"Error processing {table_name} - {execution_result}: {str(e)}")
        return False
    
def get_output_folder(input_folder: str):
    if "basic" in input_folder:
        return "response/basic_analysis_revised"
    elif "visualization" in input_folder:
        return "response/table_visualization_revised"
    elif "modeling" in input_folder:
        return "response/stat_modeling_revised"
    else:
        raise ValueError(f"Unknown input folder type: {input_folder}")
    
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_folders", required=True)
    args = parser.parse_args()
    
    input_folders = args.input_folders.split(";")
    system_prompt = read_system_prompt()
    
    for base_path in input_folders:
        output_dir = get_output_folder(base_path)
        os.makedirs(output_dir, exist_ok=True)
        
        tasks = []
        for table_name in sorted(os.listdir(base_path)):
            folder_path = os.path.join(base_path, table_name)
            if os.path.isdir(folder_path):
                for execution_result in sorted(os.listdir(folder_path)):
                    tasks.append((table_name, execution_result))
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(
                    worker,
                    table_name,
                    execution_result,
                    system_prompt,
                    base_path,
                    output_dir
                ) for table_name, execution_result in tasks
            ]
            
            for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures)):
                future.result()

if __name__ == "__main__":
    main()
