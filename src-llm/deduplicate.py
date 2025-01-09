import re


def normalize_path(path: str) -> str:
    return re.sub(r"\.\d+", ".x", path)


def deduplicate_json(data: list[dict[str, str]]) -> list[dict[str, str]]:
    """
    removes duplicate data from the list by normalizing paths for comparison
    return the original paths in the result without modification
    """

    seen: set[tuple[str, str]] = set()
    dups = 0
    unique_data: list[dict[str, str]] = []

    for item in data:
        original_path = item["path"]
        normalized_path = normalize_path(original_path)
        value = item["value"]

        if (normalized_path, value) not in seen:
            seen.add((normalized_path, value))
            unique_data.append(item)
        else:
            dups += 1
            # print(
            #     f"duplicate found. Current item: {item["path"]}, Seen item: {next(x for x in seen if x == (normalized_path, value))}"
            # )

    print(f"removed {dups} duplicates")
    return unique_data
