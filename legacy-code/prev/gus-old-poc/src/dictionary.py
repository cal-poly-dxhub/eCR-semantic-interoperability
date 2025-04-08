import json
import sys
from typing import Any

import gensim.downloader as api

from shared import save_to_file

# Download pre-trained Word2Vec model
model = api.load("word2vec-google-news-300")


def get_similar_words(query, topn=5):
    similar_words = [query]
    try:
        similar_words.extend(word for word, _ in model.most_similar(query, topn=topn))
    except KeyError:
        pass
    return similar_words


def find_relevant_pairs(data: Any, queries: list[str]) -> dict[str, Any]:
    relevant_pairs: dict[str, Any] = {}

    def traverse(obj: Any, parent_key: str):
        if isinstance(obj, dict):
            for key, value in obj.items():
                current_key = f"{parent_key}.{key}" if parent_key else key
                traverse(value, current_key)
        elif isinstance(obj, list):
            for index, value in enumerate(obj):
                current_key = f"{parent_key}[{index}]"
                traverse(value, current_key)
        else:
            for query in queries:
                if query.lower() in str(obj).lower():
                    relevant_pairs[parent_key] = obj
                    break

    traverse(data, "")
    return relevant_pairs


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python script.py <file_path> <query>")
    else:
        file = sys.argv[1]
        query = sys.argv[2]
        file_path = f"../assets/human_readable_messy/{file}"

        try:
            with open(file_path, "r") as file:
                data = json.load(file)
        except FileNotFoundError:
            print(f"Error: File '{file_path}' not found.")
        except json.JSONDecodeError:
            print(f"Error: '{file_path}' is not a valid JSON file.")
        else:
            similar_words = get_similar_words(query)
            relevant_pairs = find_relevant_pairs(data, similar_words)
            # print(json.dumps(relevant_pairs, indent=4))
            save_to_file(json.dumps(relevant_pairs, indent=4))
