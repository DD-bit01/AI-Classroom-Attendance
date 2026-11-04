import os
import csv
import cv2
import shutil
from datetime import datetime
from pathlib import Path
import database as db
from face_engine import FaceEngine

ROOT = Path('.').resolve()
PHOTOS_DIR = ROOT / 'student_photos'
PHOTOS_DIR.mkdir(exist_ok=True)

base_photos = r"D:\WpSystem\S-1-5-21-2060029638-1161821906-4011473822-1001\AppData\Local\Packages\5319275A.WhatsAppDesktop_cv1g1gvanyjgm\LocalState\sessions\0ABB8D85156C8B6330FBA94F0094F31C998DD2BF\transfers\2026-45\photos (2)\photos"

engine = FaceEngine.get_instance()
courses = db.get_all_courses()

existing_students = db.get_all_students()
existing_rolls = {s['roll_no'].strip().upper() for s in existing_students}
existing_names = {s['name'].strip().lower() for s in existing_students}

subdirs = sorted([d for d in os.listdir(base_photos) if os.path.isdir(os.path.join(base_photos, d))])

registered_count = 0
skipped_count = 0

print(f"Total folders found: {len(subdirs)}")
print(f"Existing registered students in DB: {len(existing_students)}")
print("=" * 70)

for d in subdirs:
    folder = os.path.join(base_photos, d)
    csv_path = os.path.join(folder, 'student_info.csv')
    if not os.path.exists(csv_path):
        print(f"[SKIP] No CSV in {d}")
        continue

    with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.DictReader(f)
        row = next(reader, None)
        if not row:
            continue

    roll = row.get('roll', '').strip().upper()
    name = row.get('name', '').strip()
    branch_raw = row.get('branch', '').strip().upper()
    email = row.get('email', '').strip()

    if roll in existing_rolls or name.lower() in existing_names:
        print(f"[SKIPPED - ALREADY REGISTERED] {roll} - {name}")
        skipped_count += 1
        continue

    # Branch normalization according to strict rules: CSE, AI&DS, Mech, ECE
    if branch_raw in ['AIDS', 'AI&DS', 'AI', 'AD']:
        branch = 'AI&DS'
    elif branch_raw in ['CSE', 'CS']:
        branch = 'CSE'
    elif branch_raw in ['ECE', 'EC']:
        branch = 'ECE'
    elif branch_raw in ['MECH', 'MECHANICAL', 'ME']:
        branch = 'Mech'
    else:
        branch = branch_raw

    # Destination folder
    clean_name = ''.join(c for c in name if c.isalnum() or c in (' ', '_', '-')).strip() or roll
    student_dir = PHOTOS_DIR / clean_name
    student_dir.mkdir(parents=True, exist_ok=True)

    # Process photos
    img_files = sorted([f for f in os.listdir(folder) if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
    saved_paths = []
    valid_embeddings = []
    first_photo_rel = None

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    for idx, img_name in enumerate(img_files, start=1):
        src_path = os.path.join(folder, img_name)
        img_bgr = cv2.imread(src_path)
        if img_bgr is None or img_bgr.size == 0:
            continue

        emb, err = engine.extract_single_face_embedding(img_bgr)
        if err or emb is None:
            print(f"  [Warning] Face extraction error for {name} photo {idx}: {err}")
            continue

        dest_filename = f"{roll}_{ts}_{idx}.jpg"
        dest_path = student_dir / dest_filename
        cv2.imwrite(str(dest_path), img_bgr)
        rel_path = str(dest_path.relative_to(ROOT))
        saved_paths.append(rel_path)
        valid_embeddings.append((emb, rel_path))

        if first_photo_rel is None:
            first_photo_rel = rel_path

    if not valid_embeddings:
        print(f"[ERROR] No valid face embeddings for {roll} - {name}, skipping insertion!")
        continue

    # Insert student into database
    student_id = db.add_student(
        roll_no=roll,
        name=name,
        branch=branch,
        photo_path=first_photo_rel,
        embeddings=valid_embeddings,
        email=email
    )

    # Enroll in all courses
    for c in courses:
        db.enroll_student_in_course(c['id'], student_id)

    existing_rolls.add(roll)
    existing_names.add(name.lower())
    registered_count += 1
    print(f"[REGISTERED #{registered_count:02d}] ID: {student_id:2d} | Roll: {roll:10} | Name: {name:25} | Branch: {branch:6} | Photos: {len(saved_paths)} | Vectors: {len(valid_embeddings)}")

print("=" * 70)
print(f"Batch Registration Complete! New Students Registered: {registered_count}, Already Registered Skipped: {skipped_count}")
