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


def test_windows_launcher_conda_fallback_paths_are_single_expressions():
    root = Path(__file__).resolve().parents[2]

    launcher = (root / "scripts" / "start_app.ps1").read_text()

    for conda_dir in ("miniforge3", "miniconda3", "anaconda3"):
        conda_path = f'{conda_dir}\\Scripts\\conda.exe'
        assert f'Join-Path $env:USERPROFILE "{conda_path}",' not in launcher
        assert f'(Join-Path $env:USERPROFILE "{conda_path}")' in launcher


def test_launchers_verify_the_deepseek_runtime_dependency():
    root = Path(__file__).resolve().parents[2]

    macos_linux_launcher = (root / "scripts" / "start_app.sh").read_text()
    windows_launcher = (root / "scripts" / "start_app.ps1").read_text()

    expected_probe = "import fastapi, uvicorn, langchain_deepseek"
    assert expected_probe in macos_linux_launcher
    assert expected_probe in windows_launcher
