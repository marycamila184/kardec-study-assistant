import re


def clean_markdown(text: str) -> str:
    """
    Cleans raw markdown text:
    - Removes page numbers like '# 13'
    - Removes page separators
    - Fixes hyphenated line breaks
    """
    text = re.sub(r'#\s*\d+\s*\n', '', text)
    text = re.sub(r'\n---\n', '\n', text)
    text = re.sub(r'-\n(\w+)', r'\1', text)
    return text