import os
import json

from src.parsing.cleaner import clean_markdown
from src.parsing.parser import parse_md_to_json


INPUT_DIRECTORY = "data/markdown_files"
OUTPUT_DIRECTORY = "data/json_files"


BOOK_NAME_MAP = {
    "O Livro dos Espíritos": "livro_espiritos",
    "O Livro dos Médiuns": "livro_mediuns",
    "O Evangelho Segundo o Espiritismo": "evangelho_espiritismo",
    "O Céu e o Inferno": "ceu_inferno",
    "A Gênese": "a_genese"
}


os.makedirs(OUTPUT_DIRECTORY, exist_ok=True)


def process_all_books():
    for filename in os.listdir(INPUT_DIRECTORY):

        if not filename.endswith(".md"):
            continue

        markdown_path = os.path.join(INPUT_DIRECTORY, filename)
        base_name = filename.replace(".md", "").strip()

        if base_name not in BOOK_NAME_MAP:
            print(f"Book not found in mapping dictionary: {base_name}")
            continue

        output_filename = BOOK_NAME_MAP[base_name] + ".json"
        output_path = os.path.join(OUTPUT_DIRECTORY, output_filename)

        print(f"Processing: {base_name}")

        with open(markdown_path, "r", encoding="utf-8") as f:
            markdown_text = f.read()

        cleaned_text = clean_markdown(markdown_text)
        structured_data = parse_md_to_json(cleaned_text, base_name)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(structured_data, f, ensure_ascii=False, indent=2)

        print(f"Saved to: {output_path}")

    print("\nAll books processed successfully.")


if __name__ == "__main__":
    process_all_books()
