import os
import json
from typing import List, Dict, Set, Any
from collections import defaultdict
from colorama import Fore, Style, init
import streamlit as st

init(autoreset=True)

def get_json_files(path: str) -> List[str]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Directory not found: {path}")
    
    json_files = []
    for file in os.listdir(path):
        if file.endswith(".json"):
            json_files.append(os.path.join(path, file))
    print(f"{Fore.GREEN}Found {len(json_files)} JSON files{Style.RESET_ALL}")
    return json_files

def collect_values(dictionary: Dict, value_map: defaultdict, parent_key: str = "") -> defaultdict:
    for key, value in dictionary.items():
        full_key = f"{parent_key}.{key}" if parent_key else key
        if isinstance(value, dict):
            value_map[full_key]['nested_dict'] += 1
            collect_values(value, value_map, full_key)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    value_map[full_key]['nested_dict'] += 1
                    collect_values(item, value_map, full_key)
                else:
                    value_map[full_key][str(item)] += 1
        else:
            value_map[full_key][str(value)] += 1
    return value_map

def analyze_json_directory(directory_path: str) -> Dict[str, Dict[str, int]]:
    json_files = get_json_files(directory_path)
    combined_map = defaultdict(lambda: defaultdict(int))
    
    for json_file in json_files:
        try:
            print(f"{Fore.CYAN}Processing: {os.path.basename(json_file)}{Style.RESET_ALL}")
            with open(json_file, 'r') as file:
                data = json.load(file)
            collect_values(data, combined_map)
            
        except FileNotFoundError:
            print(f"{Fore.YELLOW}Warning: File not found: {json_file}{Style.RESET_ALL}")
            continue
        except json.JSONDecodeError:
            print(f"{Fore.YELLOW}Warning: Invalid JSON format in file: {json_file}{Style.RESET_ALL}")
            continue
        except Exception as e:
            print(f"{Fore.RED}Warning: Error processing {json_file}: {str(e)}{Style.RESET_ALL}")
            continue

    result = {}
    for key, values in combined_map.items():
        if 'nested_dict' in values and len(values) > 1:
            del values['nested_dict']
        result[key] = dict(sorted(values.items(), key=lambda item: item[1], reverse=True))
    return result

def print_hierarchy(hierarchy: Dict[str, Dict[str, int]], indent: int = 0) -> None:
    for key, values in hierarchy.items():
        prefix = "  " * indent
        value_count = len(values)
        print(f"{Fore.BLUE}{prefix}{key}: {value_count} unique values{Style.RESET_ALL}")
        if value_count <= 10:
            for value, freq in values.items():
                print(f"{prefix}  {Fore.MAGENTA}{value}: {freq}{Style.RESET_ALL}")
        else:
            for value, freq in list(values.items())[:5]:
                print(f"{prefix}  {Fore.MAGENTA}{value}: {freq}{Style.RESET_ALL}")
            print(f"{prefix}  ...")
            for value, freq in list(values.items())[-5:]:
                print(f"{prefix}  {Fore.MAGENTA}{value}: {freq}{Style.RESET_ALL}")

def streamlit_interface(hierarchy: Dict[str, Dict[str, int]]):
    st.title("JSON File Analysis")
    st.write(f"Found {len(hierarchy)} unique keys across all JSON files")
    
    for key, values in hierarchy.items():
        with st.expander(f"Key: {key}"):
            st.write(f"**{len(values)} unique values**")
            st.table(values)

if __name__ == "__main__":
    try:
        path = "/Users/swayamchidrawar/repos/eCR-semantic-interoperability/semantic_matching/makedata/human_readable"
        hierarchy = analyze_json_directory(path)
        
        print("\nAnalysis Results:")
        print("-" * 50)
        print(f"{Fore.GREEN}Found {len(hierarchy)} unique keys across all JSON files{Style.RESET_ALL}")
        print("-" * 50)
        print_hierarchy(hierarchy)
        
        output_file = "json_analysis_results.json"
        with open(output_file, 'w') as f:
            json.dump(hierarchy, f, indent=2)
        print(f"\n{Fore.GREEN}Results saved to {output_file}{Style.RESET_ALL}")
        
        streamlit_interface(hierarchy)
        
    except Exception as e:
        print(f"{Fore.RED}Error: {str(e)}{Style.RESET_ALL}")
