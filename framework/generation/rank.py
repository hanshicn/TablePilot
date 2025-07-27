# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json, base64, os, argparse
from pathlib import Path
import pandas as pd
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor, as_completed

API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    raise ValueError("Please set the OPENAI_API_KEY environment variable.")

def encode_image(image_path):
    with open(image_path, 'rb') as img_file:
        return f"data:image/png;base64,{base64.b64encode(img_file.read()).decode('ascii')}"

def get_query_list(table_prompt: str, combined_results_path: str, table_name: str):
    explanation_path = os.path.join(r"response\4o_vanilla\explanation", f"{table_name}_explanations.json")
    table_theme = ""
    columns_explanation = ""
    column_relationships = ""
    
    try:
        with open(explanation_path, 'r', encoding='utf-8') as f:
            explanation_data = json.load(f)
            table_theme = explanation_data.get("Table Theme", "")
            columns_explanation = explanation_data.get("Columns", "")
            column_relationships = explanation_data.get("Column Relationships", "")
    except Exception as e:
        print(f"Warning: Failed to read explanation file for {table_name}: {str(e)}")
    
    tasks = {
        'rudimentary': [],
        'chart': [],
        'modeling': []
    }
    images = []

    for query_type in ['rudimentary', 'chart', 'modeling']:
        type_path = os.path.join(combined_results_path, query_type, table_name)
        if not os.path.exists(type_path):
            print(f"Warning: Path not found - {type_path}")
            continue

        files = os.listdir(type_path)
        for file in files:
            if not file.endswith('.txt') or 'res' in file:
                continue
            
            file_path = os.path.join(type_path, file)
            with open(file_path, 'r', encoding='utf-8') as f:
                query_text = f.read().strip()

            result_text = None
            has_image = False
            query_prefix = file.split('_')[0]

            for result_file in files:
                if result_file.startswith(query_prefix + '_res') and result_file.endswith('.png'):
                    has_image = True
                    img_path = os.path.join(type_path, result_file)
                    img_data = encode_image(img_path)
                    images.append({
                        'query_type': query_type,
                        'query': query_text,
                        'image_data': img_data  
                    })
                    break

            if not has_image:
                for result_file in files:
                    if result_file.startswith(query_prefix + '_res'):
                        if result_file.endswith('.csv'):
                            df = pd.read_csv(os.path.join(type_path, result_file))
                            num_rows, num_cols = df.shape
                            omitted_rows = 0
                            omitted_cols = 0

                            if num_rows > 10:
                                omitted_rows = num_rows - 10
                                df = df.iloc[:10, :]
                            if num_cols > 10:
                                omitted_cols = num_cols - 10
                                df = df.iloc[:, :10]

                            result_text = df.to_string(index=False)

                            # Add messages about omitted rows/columns
                            if omitted_rows > 0:
                                result_text += f"\n{omitted_rows} rows of results are omitted here"
                            if omitted_cols > 0:
                                result_text += f"\n{omitted_cols} columns of results are omitted here"

                        elif result_file.endswith('.txt'):
                            with open(os.path.join(type_path, result_file), 'r', encoding='utf-8') as rf:
                                result_text = rf.read()
                        break

            tasks[query_type].append({
                'query': query_text,
                'result': result_text if result_text else ('Image visualization available' if has_image else 'No result available')
            })

    # Construct the prompt text (excluding image data)
    prompt_text = f"""
You are provided with a portion of table data and its explanation.  Your task is to evaluate and scoring the existing data analysis queries based on this information.

Table Data:
{table_prompt}

Table Theme:
{table_theme}

Columns Explanation:
{columns_explanation}

Column Relationships:
{column_relationships}

Here are the queries and its results for the three task categories:
1. Rudimentary Data Analysis Queries:
{json.dumps(tasks['rudimentary'], ensure_ascii=False)}

2. Chart-Based Data Analysis Queries:
{json.dumps(tasks['chart'], ensure_ascii=False)}

3. Statistics Modeling Data Analysis Queries:
{json.dumps(tasks['modeling'], ensure_ascii=False)}

Task:
Please evaluate all the queries listed above across the three categories. Each query from these three types of tasks must be evaluated and assigned a score without omitting any (generally 13 queries, meaning 13 corresponding evaluation results).
Please evaluate all queries based on the six dimensions in the Ranking Criteria: Meaningful, Relative, Reasonableness, Diversity, Interpretable, Insightful. Assign a score to each dimension on a scale of 0 to 5, where a higher score indicates that the query result better aligns with that criterion. Additionally, provide an explanation for each score to justify the rating.
Be strict. Comprehensively consider all queries and results to ensure that the evaluation scores exhibit a certain degree of differentiation.
Retain the original query information exactly as it is, without making any modifications to its content. 
"""

    return {
        'prompt_text': prompt_text,
        'images': images
    }

def create_messages(system_prompt, prompt_data):
    messages = [{"role": "system", "content": [{"type": "text", "text": system_prompt}]}]
    user_content = [{"type": "text", "text": prompt_data['prompt_text']}] + [
        {"type": "image_url", "image_url": {"url": img['image_data']}} for img in prompt_data['images']]
    messages.append({"role": "user", "content": user_content})
    return messages

def get_completion(messages):
    client = OpenAI(api_key=API_KEY)
    response = client.chat.completions.create(
        model="gpt-4o-vanilla",
        messages=messages,
        max_tokens=6000,
        temperature=0.7,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "ranking_schema",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "evaluations": {
                            "type": "array",
                            "description": "A list of queries with detailed scoring and reasons",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "query": {
                                        "type": "string",
                                        "description": "The query text exactly as provided or evaluated"
                                    },
                                    "criteria": {
                                        "type": "object",
                                        "description": "Scoring details for each of the six dimensions",
                                        "properties": {
                                            "Meaningful": {
                                                "type": "object",
                                                "properties": {
                                                    "score": {
                                                        "type": "integer",
                                                        "description": "Score 0-5"
                                                    },
                                                    "reason": {
                                                        "type": "string",
                                                        "description": "Explanation for the assigned score"
                                                    }
                                                },
                                                "required": ["score", "reason"],
                                                "additionalProperties": False
                                            },
                                            "Relative": {
                                                "type": "object",
                                                "properties": {
                                                    "score": {
                                                        "type": "integer",
                                                        "description": "Score 0-5"
                                                    },
                                                    "reason": {
                                                        "type": "string",
                                                        "description": "Explanation for the assigned score"
                                                    }
                                                },
                                                "required": ["score", "reason"],
                                                "additionalProperties": False
                                            },
                                            "Reasonableness": {
                                                "type": "object",
                                                "properties": {
                                                    "score": {
                                                        "type": "integer",
                                                        "description": "Score 0-5"
                                                    },
                                                    "reason": {
                                                        "type": "string",
                                                        "description": "Explanation for the assigned score"
                                                    }
                                                },
                                                "required": ["score", "reason"],
                                                "additionalProperties": False
                                            },
                                            "Diversity": {
                                                "type": "object",
                                                "properties": {
                                                    "score": {
                                                        "type": "integer",
                                                        "description": "Score 0-5"
                                                    },
                                                    "reason": {
                                                        "type": "string",
                                                        "description": "Explanation for the assigned score"
                                                    }
                                                },
                                                "required": ["score", "reason"],
                                                "additionalProperties": False
                                            },
                                            "Interpretable": {
                                                "type": "object",
                                                "properties": {
                                                    "score": {
                                                        "type": "integer",
                                                        "description": "Score 0-5"
                                                    },
                                                    "reason": {
                                                        "type": "string",
                                                        "description": "Explanation for the assigned score"
                                                    }
                                                },
                                                "required": ["score", "reason"],
                                                "additionalProperties": False
                                            },
                                            "Insightful": {
                                                "type": "object",
                                                "properties": {
                                                    "score": {
                                                        "type": "integer",
                                                        "description": "Score 0-5"
                                                    },
                                                    "reason": {
                                                        "type": "string",
                                                        "description": "Explanation for the assigned score"
                                                    }
                                                },
                                                "required": ["score", "reason"],
                                                "additionalProperties": False
                                            }
                                        },
                                        "required": ["Meaningful", "Relative", "Reasonableness", "Diversity", "Interpretable", "Insightful"],
                                        "additionalProperties": False
                                    }
                                },
                                "required": ["query", "criteria"],
                                "additionalProperties": False
                            }
                        }
                    },
                    "required": ["evaluations"],
                    "additionalProperties": False
                }
            }
        }
    )
    return response

def worker(table_folder, system_prompt, results_path, output_dir):
    try:
        table_prompt = open(Path("our_dataset/test_table_txt") / f"{table_folder}.txt", "r", encoding="utf-8").read()
        prompt_data = get_query_list(table_prompt, results_path, table_folder)
        response_json = json.loads(get_completion(create_messages(system_prompt, prompt_data)).choices[0].message.content)
        json.dump(response_json.get("evaluations", []), open(Path(output_dir) / f"{table_folder}_ranked.json", "w", encoding="utf-8"), ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error processing {table_folder}: {str(e)}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_folder", required=True)
    parser.add_argument("--output_folder", required=True)
    args = parser.parse_args()
    os.makedirs(args.output_folder, exist_ok=True)
    
    system_prompt = open("prompt/system/ranking.md", "r", encoding="utf-8").read()
    table_folders = [f for f in os.listdir(os.path.join(args.input_folder, 'basic_analysis')) if f.startswith('table_')]
    
    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = [executor.submit(worker, table_folder, system_prompt, args.input_folder, args.output_folder) for table_folder in table_folders]
        for _ in as_completed(futures):
            pass

if __name__ == "__main__":
    main()
