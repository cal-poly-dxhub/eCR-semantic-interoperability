import re
import xml.etree.ElementTree as ET
from copy import deepcopy


def resolve_references(filepath: str) -> ET.ElementTree:
    """
    Preprocess XML file by replacing <reference> elements with actual referenced content.
    Returns a modified ElementTree with references resolved.
    """
    tree = ET.parse(filepath)
    root = tree.getroot()

    # Build ID map
    id_map = {}
    for elem in root.iter():
        elem_id = elem.get('ID') or elem.get('id')
        if elem_id:
            id_map[elem_id] = elem

    # Find and replace all reference elements
    for ref_elem in root.iter():
        if ref_elem.tag.endswith('reference'):
            ref_value = ref_elem.get('value', '')
            if ref_value.startswith('#'):
                target_id = ref_value[1:]
                if target_id in id_map:
                    target_elem = id_map[target_id]
                    parent = find_parent(root, ref_elem)
                    if parent is not None:
                        # Replace reference with a copy of the target element
                        idx = list(parent).index(ref_elem)
                        parent.remove(ref_elem)
                        parent.insert(idx, deepcopy(target_elem))

    return tree


def strip_namespaces(tree: ET.ElementTree):
    """Remove namespace URIs from all element tags and attributes in-place."""
    root = tree.getroot()
    for elem in root.iter():
        if isinstance(elem.tag, str) and '}' in elem.tag:
            elem.tag = elem.tag.split('}', 1)[1]
        new_attrib = {}
        for key, value in elem.attrib.items():
            if '}' in key:
                new_attrib[key.split('}', 1)[1]] = value
            else:
                new_attrib[key] = value
        elem.attrib.clear()
        elem.attrib.update(new_attrib)


def write_preprocessed_file(tree: ET.ElementTree, output_path: str, original_path: str):
    """Write preprocessed XML preserving the original root element and self-closing tag style."""
    content = ET.tostring(tree.getroot(), encoding="unicode")
    # Remove any residual xmlns declarations the serializer may add
    content = re.sub(r'\s*xmlns(?::\w+)?="[^"]*"', '', content)

    # Restore original root element opening tag (preserves xmlns declarations)
    with open(original_path, 'r', encoding='utf-8') as f:
        original_text = f.read()
    root_match = re.search(r'(<(?![?!])\w[^>]*>)', original_text)
    if root_match:
        original_root_tag = root_match.group(1)
        content = re.sub(r'^<\w[^>]*>', original_root_tag, content, count=1)

    # Remove space before /> in self-closing tags to match original format
    content = re.sub(r' />', '/>', content)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)
        f.write('\n')


def find_parent(root: ET.Element, target: ET.Element) -> ET.Element:
    """Find parent element of target."""
    for parent in root.iter():
        if target in list(parent):
            return parent
    return None


if __name__ == "__main__":
    import os
    import sys

    if len(sys.argv) < 2:
        print("usage: python preprocess.py <xml_file>")
        sys.exit(1)

    file = sys.argv[1]
    tree = resolve_references(file)
    strip_namespaces(tree)

    os.makedirs("out", exist_ok=True)
    output_path = os.path.join("out", os.path.basename(file).replace(".xml", "_preprocessed.xml"))
    write_preprocessed_file(tree, output_path, file)
    print(f"Saved preprocessed file: {output_path}")
