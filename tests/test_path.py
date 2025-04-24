from pathlib import Path

def test_required_files_exist():
    required_files = [
        "requirements.txt",
        ".gitignore",
        "README.md"
    ]
    
    missing = [f for f in required_files if not Path(f).exists()]
    assert not missing, f"Missing files: {missing}"