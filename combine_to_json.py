import os
import json
import argparse
from pathlib import Path

def combine_json_files(input_dir, output_file, merge_dicts=False):
    """
    Combine multiple JSON files into a single JSON file
    
    Args:
        input_dir: Directory containing JSON files to combine
        output_file: Output file path for the combined JSON
        merge_dicts: If True, merge dictionaries instead of creating a list of objects
    """
    combined_data = [] if not merge_dicts else {}
    input_path = Path(input_dir)
    
    # Check if directory exists
    if not input_path.is_dir():
        print(f"Error: Input directory '{input_dir}' does not exist.")
        return False
    
    # Get all JSON files
    json_files = list(input_path.glob('*.json'))
    if not json_files:
        print(f"No JSON files found in '{input_dir}'")
        return False
    
    print(f"Found {len(json_files)} JSON files to combine")
    
    # Process each JSON file
    for file_path in json_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if merge_dicts and isinstance(data, dict):
                    combined_data.update(data)
                else:
                    if merge_dicts:
                        print(f"Warning: {file_path.name} is not a dictionary, appending to list instead")
                        if isinstance(combined_data, dict):
                            combined_data = [combined_data]
                        combined_data.append(data)
                    else:
                        combined_data.append(data)
            print(f"Processed: {file_path.name}")
        except json.JSONDecodeError:
            print(f"Error: Could not parse {file_path.name} as JSON. Skipping.")
        except Exception as e:
            print(f"Error processing {file_path.name}: {str(e)}")
    
    # Write combined data to output file
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(combined_data, f, indent=2)
        print(f"Successfully combined {len(json_files)} JSON files into {output_file}")
        return True
    except Exception as e:
        print(f"Error writing output file: {str(e)}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Combine multiple JSON files into one")
    parser.add_argument("input_dir", help="Directory containing JSON files to combine")
    parser.add_argument("output_file", help="Output file path for the combined JSON")
    parser.add_argument("--merge", action="store_true", help="Merge dictionaries instead of creating a list")
    
    args = parser.parse_args()
    combine_json_files(args.input_dir, args.output_file, args.merge)