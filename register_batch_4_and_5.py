import os
import csv
import cv2
import hashlib
from datetime import datetime
from pathlib import Path
import database as db
from face_engine import FaceEngine

ROOT = Path('.').resolve()
PHOTOS_DIR = ROOT / 'student_photos'
PHOTOS_DIR.mkdir(exist_ok=True)

PATH_4 = r"C:\Users\Md Dilnawaz Ahmad\Downloads\photos (4)\photos"
PATH_5 = r"C:\Users\Md Dilnawaz Ahmad\Downloads\photos (5)\photos"

print("=" * 75)
print("AURA.AI — BULK REGISTRATION FOR PHOTOS (4) & PHOTOS (5)")
print("=" * 75)

# Initialize face engine
engine = FaceEngine.get_instance()
courses = db.get_all_courses()

# Fetch existing students to ensure NO duplicates
existing_students = db.get_all_students()
existing_rolls = {s['roll_no'].strip().upper() for s in existing_students}
print(f"Existing registered students in DB: {len(existing_students)}")

# Collect all student folders across both directories
student_sources = {}  # roll -> {'folders': set(), 'name': '', 'branch_raw': '', 'email': '', 'csv_data': None}

for source_path in [PATH_4, PATH_5]:
    if not os.path.exists(source_path):
        print(f"[Warning] Path does not exist: {source_path}")
        continue
    
    entries = sorted(os.listdir(source_path))
    for entry in entries:
        folder = os.path.join(source_path, entry)
        if not os.path.isdir(folder):
            continue
        
        # Read student_info.csv if present
        csv_path = os.path.join(folder, 'student_info.csv')
        row = None
        if os.path.exists(csv_path):
            try:
                with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
                    reader = csv.DictReader(f)
                    row = next(reader, None)
            except Exception as e:
                print(f"  [Warning] Error reading CSV in {folder}: {e}")
        
        roll = (row.get('roll') if row and row.get('roll') else entry).strip().upper()
        name = row.get('name', '').strip() if row else ''
        branch_raw = row.get('branch', '').strip().upper() if row else ''
        email = row.get('email', '').strip() if row else ''
        
        if roll not in student_sources:
            student_sources[roll] = {
                'folders': set(),
                'name': name,
                'branch_raw': branch_raw,
                'email': email,
                'csv_row': row
            }
        
        student_sources[roll]['folders'].add(folder)
        # Update name/email if empty
        if not student_sources[roll]['name'] and name:
            student_sources[roll]['name'] = name
        if not student_sources[roll]['email'] and email:
            student_sources[roll]['email'] = email
        if not student_sources[roll]['branch_raw'] and branch_raw:
            student_sources[roll]['branch_raw'] = branch_raw

print(f"Total unique roll numbers discovered in (4) and (5): {len(student_sources)}")

skipped_count = 0
registered_with_photos = 0
registered_no_photos = 0
total_embeddings_extracted = 0

all_rolls_sorted = sorted(student_sources.keys())

for roll in all_rolls_sorted:
    data = student_sources[roll]
    name = data['name'] or roll
    branch_raw = data['branch_raw']
    email = data['email']

    # Strict Rule 1: No duplicate roll numbers
    if roll in existing_rolls:
        print(f"[SKIP - ALREADY REGISTERED] {roll:10} | {name}")
        skipped_count += 1
        continue

    # Strict Rule 2: Follow criteria for groups / department / degree
    # - Roll contains ME / branch is MECH/MECHANICAL -> Mech
    # - Roll contains CS / branch is CSE/CS -> CSE
    # - Roll contains AD / branch is AIDS/AI&DS -> AI&DS
    # - Roll contains EC / branch is ECE/EC -> ECE
    if 'ME' in roll or branch_raw in ['MECH', 'MECHANICAL', 'ME']:
        branch = 'Mech'
    elif 'CS' in roll or branch_raw in ['CSE', 'CS']:
        branch = 'CSE'
    elif 'AD' in roll or branch_raw in ['AIDS', 'AI&DS', 'AI', 'AD']:
        branch = 'AI&DS'
    elif 'EC' in roll or branch_raw in ['ECE', 'EC']:
        branch = 'ECE'
    elif 'EE' in roll:
        branch = 'EE'
    elif 'CE' in roll:
        branch = 'Civil'
    else:
        branch = branch_raw or 'General'

    # Degree / Batch info for logging
    degree = 'Dual Degree' if roll.startswith('5') else 'B.Tech'
    batch = f"202{roll[2]}" if len(roll) >= 3 and roll[2].isdigit() else 'Unknown'

    # Destination folder for photos
    clean_name = ''.join(c for c in name if c.isalnum() or c in (' ', '_', '-')).strip() or roll
    student_dir = PHOTOS_DIR / clean_name
    student_dir.mkdir(parents=True, exist_ok=True)

    # Gather all photo files across folders, deduplicating by content hash
    seen_hashes = set()
    unique_photo_paths = []

    for folder in data['folders']:
        for fname in sorted(os.listdir(folder)):
            if fname.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                full_path = os.path.join(folder, fname)
                try:
                    with open(full_path, 'rb') as fp:
                        content_hash = hashlib.md5(fp.read()).hexdigest()
                    if content_hash not in seen_hashes:
                        seen_hashes.add(content_hash)
                        unique_photo_paths.append(full_path)
                except Exception as e:
                    print(f"  [Warning] Hash error {full_path}: {e}")

    saved_paths = []
    valid_embeddings = []
    first_photo_rel = None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Extract embeddings for unique photos
    for idx, src_path in enumerate(unique_photo_paths, start=1):
        img_bgr = cv2.imread(src_path)
        if img_bgr is None or img_bgr.size == 0:
            continue

        emb, err = engine.extract_single_face_embedding(img_bgr)
        if err or emb is None:
            print(f"  [Face Engine Warning] {roll} ({name}) photo #{idx}: {err}")
            continue

        dest_filename = f"{roll}_{ts}_{idx}.jpg"
        dest_path = student_dir / dest_filename
        cv2.imwrite(str(dest_path), img_bgr)
        rel_path = str(dest_path.relative_to(ROOT)).replace('\\', '/')
        saved_paths.append(rel_path)
        valid_embeddings.append((emb, rel_path))

        if first_photo_rel is None:
            first_photo_rel = rel_path

    # Insert student into database
    if valid_embeddings:
        student_id = db.add_student(
            roll_no=roll,
            name=name,
            branch=branch,
            photo_path=first_photo_rel,
            embeddings=valid_embeddings,
            email=email if email else None
        )
        registered_with_photos += 1
        total_embeddings_extracted += len(valid_embeddings)
        status_tag = f"ACTIVE ({len(valid_embeddings)} vectors)"
    else:
        # Student signed up without photos (e.g. pending onboarding)
        student_id = db.add_student(
            roll_no=roll,
            name=name,
            branch=branch,
            photo_path=None,
            embeddings=None,
            email=email if email else None
        )
        registered_no_photos += 1
        status_tag = "REGISTERED (0 photos, pending capture)"

    existing_rolls.add(roll)
    print(f"[REGISTERED #{registered_with_photos + registered_no_photos:02d}] ID:{student_id:3d} | {roll:10} | {name:32} | {degree:11} | {batch:5} | {branch:6} | {status_tag}")

print("=" * 75)
print(f"BATCH REGISTRATION COMPLETED!")
print(f" - Already in DB (Skipped):        {skipped_count}")
print(f" - Newly Registered with Photos:   {registered_with_photos}")
print(f" - Newly Registered (0 Photos):     {registered_no_photos}")
print(f" - Total New Students Registered:  {registered_with_photos + registered_no_photos}")
print(f" - Total Face Embeddings Added:    {total_embeddings_extracted}")
print(f" - Total Students in DB now:       {len(existing_rolls)}")
print("=" * 75)
