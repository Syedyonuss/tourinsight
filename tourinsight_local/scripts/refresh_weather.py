"""Refresh current weather cache for all active Karnataka destinations."""
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.db import connect, destination_dict, init_db
from backend.services.weather import live_weather

async def main():
    init_db()
    with connect() as conn: destinations=[destination_dict(r) for r in conn.execute("SELECT * FROM destinations WHERE active=1").fetchall()]
    success=0
    for destination in destinations:
        result=await live_weather(destination)
        if result.get("available"): success+=1
        print(f"{destination['name']}: {'updated' if result.get('available') else 'unavailable'}")
    print(f"Weather cache refresh complete: {success}/{len(destinations)} destinations refreshed.")

if __name__=="__main__": asyncio.run(main())
