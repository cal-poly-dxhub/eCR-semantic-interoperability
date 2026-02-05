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


def find_parent(root: ET.Element, target: ET.Element) -> ET.Element:
    """Find parent element of target."""
    for parent in root.iter():
        if target in list(parent):
            return parent
    return None
