import cv2
import numpy as np
from pathlib import Path
import database as db
from face_engine import get_face_engine

def reextract_all():
    fe = get_face_engine()
    conn = db.get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT e.id, e.student_id, s.name, s.roll_no, e.source_photo
        FROM student_embeddings e
        JOIN students s ON e.student_id = s.id
        ORDER BY s.id, e.id
    """)
    rows = c.fetchall()

    print(f"Re-extracting {len(rows)} embeddings...")
    updated = 0
    errors = 0

    for r in rows:
        emb_id = r["id"]
        name = r["name"]
        photo_rel = r["source_photo"]
        photo_path = Path(photo_rel)
        if not photo_path.is_absolute():
            photo_path = Path(__file__).resolve().parent / photo_path

        if not photo_path.exists():
            print(f"[ERR] File not found: {photo_path}")
            errors += 1
            continue

        img = cv2.imread(str(photo_path))
        if img is None:
            print(f"[ERR] Failed to read: {photo_path}")
            errors += 1
            continue

        emb, err = fe.extract_single_face_embedding(img)
        if err or emb is None:
            print(f"[ERR] Face extraction failed for {name} ({photo_rel}): {err}")
            errors += 1
            continue

        c.execute("UPDATE student_embeddings SET vector = ? WHERE id = ?", (emb.tobytes(), emb_id))
        updated += 1

    conn.commit()
    conn.close()
    print(f"\nDone! Successfully updated: {updated}, Errors: {errors}")

if __name__ == "__main__":
    reextract_all()
