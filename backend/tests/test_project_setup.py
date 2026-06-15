from pathlib import Path


def test_backend_entrypoint_exists():
    root = Path(__file__).resolve().parents[2]

    assert (root / "backend" / "app" / "__init__.py").is_file()
    assert (root / "backend" / "app" / "main.py").is_file()
