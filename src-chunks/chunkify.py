from typing import Any, Union


def find_last_section(
    data: dict[str, Any], section: str
) -> Union[dict[str, Any], None]:
    """
    recursively find the last occurrence of the specified section in the JSON data.
    """
    if section in data:
        last_section = data[section]
    else:
        last_section = None

    for _, value in data.items():
        if isinstance(value, dict):
            nested_section = find_last_section(value, section)  # type: ignore
            if nested_section is not None:
                last_section = nested_section

    return last_section


def chunkify_json(
    data: dict[str, Union[str, list[dict[str, Any]]]]
) -> list[dict[str, Any]]:
    """
    chunkify JSON by finding the last nested hardcoded sections.
    """
    chunks: list[dict[str, Any]] = []

    sections = [
        "act",
        "recordTarget",
        "author",
        "custodian",
        "relatedDocument",
        "componentOf",
        "component",
    ]

    for section in sections:
        last_section = find_last_section(data, section)
        if last_section is not None:
            if isinstance(last_section, dict):  # type: ignore
                chunks.append(last_section)
            elif isinstance(last_section, list):  # type: ignore
                chunks.extend(last_section)

    remaining_data = {key: value for key, value in data.items() if key not in sections}
    if remaining_data:
        chunks.append(remaining_data)

    return chunks
