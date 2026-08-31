import sys
import os
from datetime import timedelta

sys.path.insert(0, r"c:\Users\radhi\OneDrive\Desktop\final_prototype\backend")

from app.db.session import SessionLocal
from app.db.models import AgentRun

def repair():
    db = SessionLocal()
    runs = db.query(AgentRun).all()
    repaired = 0
    for r in runs:
        if r.started_at and r.completed_at and r.completed_at < r.started_at:
            print(f"Repairing AgentRun {r.id}: started_at={r.started_at}, old_completed_at={r.completed_at}")
            r.completed_at = r.started_at + timedelta(seconds=1)
            repaired += 1
            
    db.commit()
    db.close()
    print(f"Successfully repaired {repaired} runs.")

if __name__ == "__main__":
    repair()
