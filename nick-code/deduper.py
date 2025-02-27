from lxml import etree as ET
from typing import Dict, List, Tuple, Set
import json
from dataclasses import dataclass
from collections import defaultdict
import argparse
import os
import glob

@dataclass
class DedupResult:
    deduped_xml: str
    removed_elements: List[Dict[str, str]]

def normalize_element(elem: ET.Element) -> dict:
    result = {
        'tag': elem.tag,
        'text': (elem.text or '').strip(),
        'tail': (elem.tail or '').strip(),
        'attrib': dict(sorted(elem.attrib.items())),
        'children': []
    }
    
    for child in elem:
        result['children'].append(normalize_element(child))
    
    return result

def elements_are_equal(elem1: ET.Element, elem2: ET.Element) -> bool:
    return json.dumps(normalize_element(elem1)) == json.dumps(normalize_element(elem2))

def find_duplicates(root: ET.Element) -> Dict[str, List[List[ET.Element]]]:
    duplicates = defaultdict(list)
    
    for elem in root.iter():
        tag = elem.tag
        found_match = False
        
        for group in duplicates[tag]:
            if elements_are_equal(elem, group[0]):
                group.append(elem)
                found_match = True
                break
                
        if not found_match:
            duplicates[tag].append([elem])
    
    return duplicates

def remove_duplicates(xml_string: str) -> DedupResult:
    root = ET.fromstring(xml_string)
    duplicates = find_duplicates(root)
    removed = []
    
    for tag, groups in duplicates.items():
        for group in groups:
            if len(group) > 1:
                for elem in group[1:]:
                    removed.append({
                        'tag': tag,
                        'content': ET.tostring(elem, encoding='unicode')
                    })
                    parent = elem.getparent()
                    if parent is not None:
                        parent.remove(elem)
    
    return DedupResult(
        deduped_xml=ET.tostring(root, encoding='unicode'),
        removed_elements=removed
    )

def deduplicate_file(input_path: str, output_path: str) -> List[Dict[str, str]]:
    with open(input_path, 'r') as f:
        xml_content = f.read()
    
    result = remove_duplicates(xml_content)
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w') as f:
        f.write(result.deduped_xml)
    
    return result.removed_elements

def process_directory(input_dir: str, output_dir: str, log_path: str = None):
    if not os.path.exists(input_dir):
        raise ValueError(f"Input directory does not exist: {input_dir}")
    
    os.makedirs(output_dir, exist_ok=True)
    all_removed = []
    
    for xml_file in glob.glob(os.path.join(input_dir, "*.xml")):
        filename = os.path.basename(xml_file)
        output_path = os.path.join(output_dir, filename)
        
        try:
            removed = deduplicate_file(xml_file, output_path)
            all_removed.append({
                'file': filename,
                'removed': removed
            })
            print(f"Processed {filename}: removed {len(removed)} duplicates")
        except Exception as e:
            print(f"Error processing {filename}: {str(e)}")
    
    if log_path and all_removed:
        with open(log_path, 'w') as f:
            json.dump(all_removed, f, indent=2)

def main():
    parser = argparse.ArgumentParser(description='Remove duplicate elements from XML files')
    parser.add_argument('input', help='Input XML file or directory path')
    parser.add_argument('output', help='Output file or directory path')
    parser.add_argument('--log', help='Optional log file for removed elements')
    args = parser.parse_args()

    if os.path.isdir(args.input):
        process_directory(args.input, args.output, args.log)
    else:
        removed = deduplicate_file(args.input, args.output)
        if args.log:
            with open(args.log, 'w') as f:
                json.dump(removed, f, indent=2)
            print(f"Removed {len(removed)} duplicate elements. See {args.log} for details.")
        else:
            print(f"Removed {len(removed)} duplicate elements.")

if __name__ == "__main__":
    main()