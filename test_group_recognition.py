"""
AURA // Automated Group Recognition Test Script
Tests facial detection & recognition across all images in test_images/
using enrolled student embeddings from SQLite (database.py).
"""

import cv2
import numpy as np
from pathlib import Path
import os
import sys
import argparse
import base64
import database as db
from face_engine import get_face_engine

ROOT = Path(__file__).resolve().parent
IMAGE_DIR = ROOT / "test_images"
OUTPUT_DIR = ROOT / "annotated_samples"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_THRESHOLD = 0.35

def run_tests(target_path=None, threshold=DEFAULT_THRESHOLD):
    engine = get_face_engine()

    # Load all registered student embeddings from database
    conn = db.get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT e.student_id, s.roll_no, s.name, s.branch, e.vector
        FROM student_embeddings e
        JOIN students s ON e.student_id = s.id
    """)
    rows = c.fetchall()
    conn.close()

    if not rows:
        print("[!] No student embeddings found in database. Register students first.")
        return

    embeddings = [np.frombuffer(r["vector"], dtype=np.float32) for r in rows]
    student_ids = [r["student_id"] for r in rows]
    meta = {r["student_id"]: {"roll_no": r["roll_no"], "name": r["name"], "branch": r["branch"]} for r in rows}

    known_embs = np.asarray(embeddings, dtype=np.float32)
    known_ids = np.asarray(student_ids)

    print("\n" + "=" * 60)
    print(f" AURA Face Engine // Multi-Face Group Recognition")
    print(f" Enrolled Students : {len(meta)} students ({len(known_ids)} total embeddings)")
    print(f" Cosine Threshold  : {threshold}")
    print("=" * 60 + "\n")

    extensions = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    
    if target_path:
        p = Path(target_path)
        if not p.is_absolute():
            # Check current dir, then test_images/
            if p.exists():
                images = [p]
            elif (IMAGE_DIR / p.name).exists():
                images = [IMAGE_DIR / p.name]
            else:
                print(f"[!] File not found: {target_path}")
                return
        else:
            if not p.exists():
                print(f"[!] File not found: {target_path}")
                return
            images = [p]
    else:
        images = sorted([p for p in IMAGE_DIR.iterdir() if p.is_file() and p.suffix.lower() in extensions])

    if not images:
        print(f"[!] No images found to test in: {IMAGE_DIR}")
        print("    Place your group photo in the 'test_images' folder and try again.")
        return

    for img_path in images:
        filename = img_path.name
        img = cv2.imread(str(img_path))
        if img is None:
            print(f"[!] Unable to decode image: {img_path}")
            continue

        dets, annotated_b64 = engine.recognize_faces_in_image(
            img,
            known_embeddings=known_embs,
            known_student_ids=known_ids,
            id_meta_map=meta,
            threshold=threshold,
            draw_annotations=True
        )

        matched = [d for d in dets if d["is_matched"]]
        unknowns = [d for d in dets if not d["is_matched"]]

        print(f"--> [{filename}] Detected Faces: {len(dets)} | Matches: {len(matched)} | Unknowns: {len(unknowns)}")
        
        if matched:
            print("    [MATCHES]:")
            for m in sorted(matched, key=lambda x: x["score"], reverse=True):
                print(f"       * {m['name']} ({m['roll_no']}) -> {m['score']*100:.1f}% confidence")
        if unknowns:
            print(f"    [UNKNOWNS]: {len(unknowns)} face(s) mapped to 'Unknown'")

        # Save annotated image
        if annotated_b64:
            out_file = OUTPUT_DIR / f"annotated_{filename}"
            with open(out_file, "wb") as f:
                f.write(base64.b64decode(annotated_b64.split(",")[-1]))
            print(f"    Saved visual prediction to: {out_file.relative_to(ROOT)}")
        print("-" * 60)

    print(f"\n[DONE] Check your annotated predictions in: {OUTPUT_DIR}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AURA Group Face Recognition Tester")
    parser.add_argument("image", nargs="?", default=None, help="Optional path or filename of a specific group photo")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD, help="Cosine similarity threshold (default: 0.36)")
    args = parser.parse_args()

    run_tests(target_path=args.image, threshold=args.threshold)
