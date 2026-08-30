from pathlib import Path
import os


API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
DATA_ROOT = Path(os.getenv("DRAMA_DATA_ROOT", REPO_ROOT / "data")).resolve()
DATABASE_PATH = Path(os.getenv("DRAMA_DATABASE_PATH", DATA_ROOT / "phase1.sqlite3")).resolve()
STORAGE_ROOT = Path(os.getenv("DRAMA_STORAGE_ROOT", DATA_ROOT / "storage")).resolve()

