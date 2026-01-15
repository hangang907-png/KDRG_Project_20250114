import json
import os
from typing import Any, Dict, List, Optional

import aiosqlite

from config import settings


class GroupingStore:
    def __init__(self, db_url: str):
        self.db_path = self._extract_path(db_url)
        self._initialized = False

    def _extract_path(self, db_url: str) -> str:
        if db_url.startswith("sqlite+aiosqlite:///"):
            return db_url.replace("sqlite+aiosqlite:///", "", 1)
        if db_url.startswith("sqlite:///"):
            return db_url.replace("sqlite:///", "", 1)
        return db_url

    async def _init(self):
        if self._initialized:
            return
        if self.db_path:
            os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS grouping_history (
                    history_id TEXT PRIMARY KEY,
                    created_at TEXT,
                    type TEXT,
                    payload_json TEXT
                )
                """
            )
            await db.commit()
        self._initialized = True

    async def save_history(self, history_id: str, history_type: str, payload: Dict[str, Any]):
        await self._init()
        payload_json = json.dumps(payload, ensure_ascii=False)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO grouping_history (history_id, created_at, type, payload_json) VALUES (?, ?, ?, ?)",
                (history_id, payload.get("created_at"), history_type, payload_json),
            )
            await db.commit()

    async def list_history(self, limit: int = 50) -> Dict[str, Any]:
        await self._init()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT history_id, created_at, type, payload_json FROM grouping_history ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            rows = await cursor.fetchall()

        history_list = []
        for row in rows:
            payload = json.loads(row["payload_json"])
            history_list.append(
                {
                    "history_id": row["history_id"],
                    "created_at": row["created_at"],
                    "type": row["type"],
                    "patient_id": payload.get("input", {}).get("patient_id", ""),
                    "total": payload.get("total", 1),
                    "success_count": payload.get("success_count", 1),
                }
            )

        return {"success": True, "total": len(history_list), "history": history_list}

    async def get_history(self, history_id: str) -> Optional[Dict[str, Any]]:
        await self._init()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT history_id, created_at, type, payload_json FROM grouping_history WHERE history_id = ?",
                (history_id,),
            )
            row = await cursor.fetchone()

        if not row:
            return None

        payload = json.loads(row["payload_json"])
        return {
            "history_id": row["history_id"],
            "created_at": row["created_at"],
            "type": row["type"],
            **payload,
        }

    async def delete_history(self, history_id: str) -> bool:
        await self._init()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("DELETE FROM grouping_history WHERE history_id = ?", (history_id,))
            await db.commit()
            return cursor.rowcount > 0

    async def get_statistics(self) -> Dict[str, Any]:
        await self._init()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT payload_json, type FROM grouping_history")
            rows = await cursor.fetchall()

        type_stats: Dict[str, int] = {"single": 0, "batch": 0, "upload": 0}
        drg_type_counts: Dict[str, int] = {}
        total_estimated = 0
        total_groupings = len(rows)

        for row in rows:
            payload = json.loads(row["payload_json"])
            hist_type = row["type"] or payload.get("type", "single")
            type_stats[hist_type] = type_stats.get(hist_type, 0) + 1

            results = payload.get("results")
            if isinstance(results, list):
                for r in results:
                    drg_type = r.get("drg_type", "행위별")
                    drg_type_counts[drg_type] = drg_type_counts.get(drg_type, 0) + 1
                    total_estimated += r.get("estimated_amount", 0)
            elif "result" in payload:
                r = payload.get("result", {})
                drg_type = r.get("drg_type", "행위별")
                drg_type_counts[drg_type] = drg_type_counts.get(drg_type, 0) + 1
                total_estimated += r.get("estimated_amount", 0)

        return {
            "success": True,
            "total_groupings": total_groupings,
            "by_type": type_stats,
            "by_drg_type": drg_type_counts,
            "total_estimated_amount": total_estimated,
        }


grouping_store = GroupingStore(settings.DATABASE_URL)
