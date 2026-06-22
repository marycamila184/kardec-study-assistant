import json
import pytest
from src.api.paths import load_all_paths, load_path

_PATH_DATA = {
    "id": "fundamentos",
    "title": "Fundamentos",
    "description": "Para iniciantes.",
    "level": "iniciante",
    "steps": [
        {"book": "O Livro dos Espíritos", "item_number": "1", "label": "O que é Deus?"},
        {"book": "O Livro dos Espíritos", "item_number": "2", "label": "Atributos da divindade"},
    ],
}


@pytest.fixture
def paths_dir(tmp_path):
    (tmp_path / "fundamentos.json").write_text(
        json.dumps(_PATH_DATA, ensure_ascii=False), encoding="utf-8"
    )
    return str(tmp_path)


def test_load_all_paths_returns_summaries(paths_dir):
    paths = load_all_paths(paths_dir)
    assert len(paths) == 1
    assert paths[0]["id"] == "fundamentos"
    assert paths[0]["step_count"] == 2
    assert "steps" not in paths[0]


def test_load_all_paths_returns_empty_when_dir_missing():
    paths = load_all_paths("/nonexistent/path/xyz")
    assert paths == []


def test_load_all_paths_ignores_non_json_files(paths_dir, tmp_path):
    (tmp_path / "notes.txt").write_text("ignore me")
    paths = load_all_paths(paths_dir)
    assert len(paths) == 1


def test_load_path_returns_full_detail_with_steps(paths_dir):
    path = load_path(paths_dir, "fundamentos")
    assert path["id"] == "fundamentos"
    assert len(path["steps"]) == 2
    assert path["steps"][0]["item_number"] == "1"


def test_load_path_returns_none_when_not_found(paths_dir):
    result = load_path(paths_dir, "nonexistent")
    assert result is None
