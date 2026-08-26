import os
import json
from datetime import datetime, date
from typing import Dict, Any, List, Set, Optional
from src.logger import log_info, log_warning

DEFAULT_HISTORY_FILE = "solved_history.json"

class HistoryTracker:
    def __init__(self, filepath: str = DEFAULT_HISTORY_FILE):
        self.filepath = filepath
        self.data: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        """Loads existing history from JSON file."""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                log_warning(f"Could not load history file {self.filepath}: {e}. Initializing new history.")
        return {"solved_problems": {}, "daily_counts": {}}

    def save(self) -> None:
        """Saves current history back to JSON file."""
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            log_warning(f"Could not save history to {self.filepath}: {e}")

    def is_solved(self, title_slug: str) -> bool:
        """Checks if a problem slug has already been recorded as solved."""
        return title_slug in self.data.get("solved_problems", {})

    def get_solved_slugs(self) -> Set[str]:
        """Returns set of all solved problem slugs."""
        return set(self.data.get("solved_problems", {}).keys())

    def record_solution(
        self,
        title_slug: str,
        title: str,
        frontend_id: str,
        difficulty: str,
        mode: str,
        winner_model: Optional[str] = None
    ) -> None:
        """Records a successfully solved problem."""
        today_str = date.today().isoformat()
        now_str = datetime.now().isoformat()

        if "solved_problems" not in self.data:
            self.data["solved_problems"] = {}
        if "daily_counts" not in self.data:
            self.data["daily_counts"] = {}

        self.data["solved_problems"][title_slug] = {
            "title": title,
            "frontend_id": frontend_id,
            "difficulty": difficulty,
            "mode": mode,
            "solved_at": now_str,
            "date": today_str,
            "winner_model": winner_model
        }

        # Update daily count
        daily_record = self.data["daily_counts"].get(today_str, {"potd": 0, "extra": 0, "total": 0})
        if mode == "potd":
            daily_record["potd"] = daily_record.get("potd", 0) + 1
        else:
            daily_record["extra"] = daily_record.get("extra", 0) + 1
        daily_record["total"] = daily_record.get("total", 0) + 1
        self.data["daily_counts"][today_str] = daily_record

        self.save()
        log_info(f"Recorded problem '{title_slug}' in history. Total solved today: {daily_record['total']}")

    def get_today_progress(self) -> Dict[str, int]:
        """Returns statistics for problems solved today."""
        today_str = date.today().isoformat()
        return self.data.get("daily_counts", {}).get(today_str, {"potd": 0, "extra": 0, "total": 0})
