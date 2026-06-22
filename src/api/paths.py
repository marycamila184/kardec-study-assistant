import json
import os


def load_all_paths(paths_dir: str) -> list[dict]:
    if not os.path.isdir(paths_dir):
        return []
    summaries = []
    for filename in sorted(os.listdir(paths_dir)):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(paths_dir, filename)
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
        summaries.append(
            {
                "id": data["id"],
                "title": data["title"],
                "description": data["description"],
                "level": data["level"],
                "step_count": len(data["steps"]),
            }
        )
    return summaries


def load_path(paths_dir: str, path_id: str) -> dict | None:
    filepath = os.path.join(paths_dir, f"{path_id}.json")
    if not os.path.exists(filepath):
        return None
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)
