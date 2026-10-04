import asyncio
import httpx
import json
import sqlite3
from pathlib import Path

API_URL = "http://localhost:8000/api/v1"
DB_PATH = "dev_local.db"
OUTPUT_FILE = Path(".backup/golden_snapshots.json")

from backend.auth import create_access_token

async def capture_snapshots():
    token = create_access_token({"sub": "1", "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(base_url=API_URL, timeout=30.0, headers=headers) as client:
        # Get 15 conversations
        res = await client.get("/conversations?limit=15")
        if res.status_code != 200:
            print(f"Failed to get conversations: {res.status_code} {res.text}")
        res.raise_for_status()
        conversations = res.json()
        
        snapshots = {
            "conversations_list": conversations,
            "conversation_details": {},
            "analytics_overview": None,
            "table_counts": {}
        }
        
        # Get details for the 15 conversations
        if isinstance(conversations, dict) and "items" in conversations:
            conv_list = conversations["items"]
        else:
            conv_list = conversations
            
        for conv in conv_list[:15]:
            conv_id = conv["id"]
            detail = await client.get(f"/conversations/{conv_id}")
            snapshots["conversation_details"][conv_id] = detail.json()
            
        # Get analytics endpoints
        analytics_res = await client.get("/analytics/overview")
        if analytics_res.status_code == 200:
            snapshots["analytics_overview"] = analytics_res.json()
            
        # DB Table counts
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
            count = cursor.fetchone()[0]
            snapshots["table_counts"][table_name] = count
        conn.close()
        
        OUTPUT_FILE.parent.mkdir(exist_ok=True)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(snapshots, f, indent=2)
        print(f"Captured golden snapshots and saved to {OUTPUT_FILE}")
        for t, c in snapshots["table_counts"].items():
            print(f"Table {t}: {c} rows")

if __name__ == "__main__":
    asyncio.run(capture_snapshots())
