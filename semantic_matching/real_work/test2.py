import json
import json_lines

def parse_jsonl_file(file_path):
    results = []
    try:
        with open(file_path, 'r') as f:
            for line in f:
                try:
                    # Parse each line as JSON
                    data = json.loads(line)
                    # Extract relevant fields
                    model_input = data.get('modelInput', {}).get('messages', [{}])[0].get('content', [{}])[0].get('text', '')
                    model_output = data.get('modelOutput', {}).get('content', [{}])[0].get('text', '')
                    results.append({
                        'input_text': model_input,
                        'output_text': model_output
                    })
                except json.JSONDecodeError as e:
                    print(f"Error parsing JSON: {e}")
                except Exception as e:
                    print(f"Unexpected error: {e}")
        return results
    except FileNotFoundError:
        print(f"File {file_path} not found.")
        return []
    except Exception as e:
        print(f"An error occurred: {e}")
        return []

def save_results_to_file(results, filename):
    try:
        with open(filename, 'w') as f:
            json.dump(results, indent=2, ensure_ascii=False, fp=f)
        print(f"Results saved to: {filename}")
        return True
    except Exception as e:
        print(f"Error saving results: {e}")
        return False

def main():
    file_path = 'downloaded_results.jsonl.out'  # Update this to your file path
    results = parse_jsonl_file(file_path)
    
    if results:
        print("\nParsed Results:")
        for i, result in enumerate(results, 1):
            print(f"\nResult {i}:")
            print(f"Input: {result['input_text']}")
            print(f"Output: {result['output_text']}")
        
        # Save results to a new file
        filename = input("\nEnter a filename to save results (default: 'parsed_results.json'): ") or 'parsed_results.json'
        save_results_to_file(results, filename)
        print(f"\nTotal results parsed: {len(results)}")
    else:
        print("No results found.")

if __name__ == "__main__":
    main()
