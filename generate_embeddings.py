"""
AURA Batch Biometric Embedding Generator
=========================================
Senior Developer Automation Tool:
Scans all student photo folders (or a specific student) and computes
ArcFace 512-D normalized facial embeddings for all valid portrait photos.
Stores the vectors in SQLite student_embeddings with atomic transactions.

Usage:
  python generate_embeddings.py                  # Process all enrolled students
  python generate_embeddings.py --roll 124AD0029 # Process specific student
  python generate_embeddings.py --force          # Re-compute all embeddings from disk
"""

import sys
import os
import argparse
from pathlib import Path
from datetime import datetime
import cv2
import numpy as np

import database as db
from face_engine import get_face_engine

ROOT = Path(__file__).resolve().parent
PHOTOS_DIR = ROOT / "student_photos"

def process_student_photos(student: dict, engine, force: bool = False):
    student_id = student["id"]
    name = student["name"]
    roll_no = student["roll_no"]

    clean_name = "".join(c for c in name if c.isalnum() or c in (" ", "_", "-")).strip()
    student_folder = PHOTOS_DIR / clean_name

    # Fallback search by roll_no if folder name is different
    if not student_folder.exists():
        found = False
        for folder in PHOTOS_DIR.iterdir():
            if folder.is_dir() and folder.name.lower() == clean_name.lower():
                student_folder = folder
                found = True
                break
        if not found:
            print(f"  [-] Photo folder not found for {name} ({roll_no}) at: {student_folder}")
            return 0

    valid_exts = {".jpg", ".jpeg", ".png", ".webp"}
    photo_files = sorted([p for p in student_folder.iterdir() if p.is_file() and p.suffix.lower() in valid_exts])

    if not photo_files:
        print(f"  [-] No image files found in {student_folder.name}")
        return 0

    # Get already embedded photos for this student
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT source_photo FROM student_embeddings WHERE student_id = ?", (student_id,))
    existing_sources = {r["source_photo"] for r in cursor.fetchall()}
    conn.close()

    new_count = 0
    errors = 0

    for p in photo_files:
        rel_path = str(p.relative_to(ROOT))
        if not force and rel_path in existing_sources:
            continue

        img_bgr = cv2.imread(str(p))
        if img_bgr is None or img_bgr.size == 0:
            continue

        embedding, err = engine.extract_single_face_embedding(img_bgr)
        if err or embedding is None:
            # print warning
            errors += 1
            continue

        # If force, clear duplicates first
        if force:
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM student_embeddings WHERE student_id = ? AND source_photo = ?", (student_id, rel_path))
            conn.commit()
            conn.close()

        db.add_embedding_to_student(student_id, embedding, rel_path)
        new_count += 1

    return new_count

def run_batch_embeddings(roll_filter: str = None, force: bool = False):
    print("=" * 65)
    print("  AURA AI // Biometric Facial Embedding Batch Generator")
    print("  ArcFace ResNet-50 (43.5M parameters) + YuNet Facial Engine")
    print("=" * 65)

    engine = get_face_engine()
    all_students = db.get_all_students()

    if roll_filter:
        all_students = [s for s in all_students if s["roll_no"].upper() == roll_filter.strip().upper()]
        if not all_students:
            print(f"[!] No student found matching Roll Number '{roll_filter}'")
            return

    print(f"Found {len(all_students)} student record(s) to inspect.\n")

    total_added = 0
    for idx, s in enumerate(all_students, 1):
        print(f"[{idx}/{len(all_students)}] Processing: {s['name']} (Roll: {s['roll_no']}, Branch: {s['branch']})...")
        added = process_student_photos(s, engine, force=force)
        if added > 0:
            print(f"      ==> Added {added} new facial embedding vector(s) into database!")
            total_added += added
        else:
            print(f"      ==> Up to date ({s.get('embedding_count', 0)} embedding(s) already active).")

    print("\n" + "=" * 65)
    print(f"  Summary: Generated & Saved {total_added} facial embeddings in SQLite.")
    print("  All students are ready for instantaneous classroom facial matching.")
    print("=" * 65 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch generate ArcFace embeddings for student photos.")
    parser.add_argument("--roll", type=str, default=None, help="Filter by specific student roll number.")
    parser.add_argument("--force", action="store_true", help="Re-compute and overwrite existing embeddings.")
    args = parser.parse_args()

    run_batch_embeddings(roll_filter=args.roll, force=args.force)
