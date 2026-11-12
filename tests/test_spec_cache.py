from pathlib import Path

from biflow.tools import spec_cache
from biflow.tools.spec_cache import cache_key, catalog_sha256, code_sha256, generated_path, pregenerate


def _warehouse(tmp_path: Path) -> Path:
    path = tmp_path / "warehouse.duckdb"
    path.write_bytes(b"w")
    return path


def test_catalog_or_code_hash_changes_the_cache_file(tmp_path):
    warehouse = _warehouse(tmp_path)
    base = cache_key(warehouse, catalog_hash="a" * 64, code_hash="b" * 64)
    other_catalog = cache_key(warehouse, catalog_hash="c" * 64, code_hash="b" * 64)
    other_code = cache_key(warehouse, catalog_hash="a" * 64, code_hash="d" * 64)
    paths = {generated_path(tmp_path, "MAR", 2024, key) for key in (base, other_catalog, other_code)}
    assert len(paths) == 3


def test_hashes_follow_file_content(tmp_path):
    catalog = tmp_path / "catalog.yaml"
    catalog.write_text("catalog_version: '1'\n", encoding="utf-8")
    code = tmp_path / "builder.py"
    code.write_text("A = 1\n", encoding="utf-8")
    before = catalog_sha256(catalog), code_sha256([code])
    catalog.write_text("catalog_version: '2'\n", encoding="utf-8")
    code.write_text("A = 2  # uncommitted edit\n", encoding="utf-8")
    after = catalog_sha256(catalog), code_sha256([code])
    assert before[0] != after[0] and before[1] != after[1]


def test_default_code_files_exist():
    assert all(path.is_file() for path in spec_cache.CODE_FILES)


def test_old_key_format_is_ignored_and_kept(tmp_path):
    warehouse = _warehouse(tmp_path)
    root = tmp_path / "generated"
    root.mkdir()
    old = root / f"MAR_2024_{int(warehouse.stat().st_mtime)}.json"
    old.write_text('{"stale": true}', encoding="utf-8")
    built = []

    def builder(iso3, year):
        built.append((iso3, year))
        return {"pages": [{"id": "overview"}]}

    done = pregenerate(builder, root, warehouse, [("MAR", 2024)])
    assert built == [("MAR", 2024)] and done[0]["status"] == "generated"
    assert Path(done[0]["path"]).name != old.name
    assert old.is_file()
