from bs4 import BeautifulSoup
import os
from datetime import datetime

def parse_xml_to_readable(xml_path, output_folder):
    # Read the XML file
    with open(xml_path, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # Parse XML using BeautifulSoup
    soup = BeautifulSoup(content, 'xml')
    
    # Create output folder if it doesn't exist
    os.makedirs(output_folder, exist_ok=True)
    
    # Generate output filename using timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = os.path.join(output_folder, f'parsed_xml_{timestamp}.txt')
    
    # Function to recursively process XML elements
    def process_element(element, level=0):
        output = []
        indent = "    " * level  # 4 spaces per level
        
        # Handle text nodes
        if element.string and element.string.strip():
            return [f"{indent}{element.name}: {element.string.strip()}"]
        
        # Handle elements with attributes
        if element.attrs:
            attrs_str = ", ".join([f"{k}='{v}'" for k, v in element.attrs.items()])
            output.append(f"{indent}{element.name} [{attrs_str}]")
        else:
            output.append(f"{indent}{element.name}")
        
        # Process child elements
        for child in element.children:
            if child.name:  # Skip NavigableString objects
                output.extend(process_element(child, level + 1))
        
        return output
    
    # Process the XML and write to file
    with open(output_file, 'w', encoding='utf-8') as file:
        # Write header
        file.write(f"XML File: {os.path.basename(xml_path)}\n")
        file.write(f"Parsed on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        file.write("=" * 50 + "\n\n")
        
        # Write parsed content
        for line in process_element(soup.find_all()[0]):
            file.write(line + "\n")
    
    return output_file

# Example usage
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 3:
        print("Usage: python script.py <xml_file_path> <output_folder_path>")
        sys.exit(1)
    
    xml_path = sys.argv[1]
    output_folder = sys.argv[2]
    
    try:
        output_file = parse_xml_to_readable(xml_path, output_folder)
        print(f"Successfully parsed XML. Output saved to: {output_file}")
    except Exception as e:
        print(f"Error: {str(e)}")