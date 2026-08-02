from pathlib import Path

def ensure_output_dirs() -> None:
    """Create standard benchmark output folders if they do not exist."""
    Path("results").mkdir(parents=True, exist_ok=True)
    Path("submissions").mkdir(parents=True, exist_ok=True)
