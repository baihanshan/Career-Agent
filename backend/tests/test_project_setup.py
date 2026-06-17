from pathlib import Path


def test_backend_entrypoint_exists():
    root = Path(__file__).resolve().parents[2]

    assert (root / "backend" / "app" / "__init__.py").is_file()
    assert (root / "backend" / "app" / "main.py").is_file()


def test_sprint2_local_retrieval_configuration_is_documented():
    root = Path(__file__).resolve().parents[2]

    requirements = (root / "requirements-dev.txt").read_text()
    pyproject = (root / "pyproject.toml").read_text()
    env_example = (root / ".env.example").read_text()
    readme = (root / "README.md").read_text()

    for dependency in ("sentence-transformers", "chromadb"):
        assert dependency in requirements
        assert dependency in pyproject

    assert "BGE_MODEL_NAME=BAAI/bge-large-zh-v1.5" in env_example
    assert "BGE_MODEL_CACHE_DIR=/Users/baihanshan/Desktop/bge-models" in env_example
    assert "CHROMA_PATH=/Users/baihanshan/Desktop/career-agent-chroma" in env_example
    assert "BGE_MODEL_CACHE_DIR" in readme
    assert "CHROMA_PATH" in readme
