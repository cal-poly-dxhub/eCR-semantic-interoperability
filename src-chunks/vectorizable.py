from typing import Any, Union


def vectorize_tables(
    data: list[dict[str, Union[str, list[dict[str, Any]]]]]
) -> list[str]:
    """
    vectorize json tables into a list of strings
    """
    vectorized: list[str] = []
    for table in data:
        table = table["table"]
        # table could be a list of tables
        if not isinstance(table, list):
            table = [table]
            # for
            thead = table.get("thead", {}).get("tr", {}).get("th", [])  # type: ignore
            tbody = table.get("tbody", {}).get("tr", {}).get("td", [])  # type: ignore

            # get the headers
            headers = [t["content"] for t in thead]  # type: ignore
            rows = [r["content"] for r in tbody if "content" in r]  # type: ignore

            # vectorize the table
            vectorized.append(" ".join(headers))  # type: ignore
            vectorized.append(" ".join([str(row) for row in rows]))  # type: ignore

    return vectorized
