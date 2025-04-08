def save_to_file(s: str, file_path: str = "output.json") -> None:
    with open(file_path, "w") as file:
        file.write(s)
