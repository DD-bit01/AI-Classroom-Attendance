import cv2
import numpy as np
import base64
import os
import shutil
import database as db
from face_engine import get_face_engine

def run_recognition():
    engine = get_face_engine()
    
    # 1. Fetch all registered student embeddings from database
    conn = db.get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT e.student_id, s.roll_no, s.name, s.branch, e.vector
        FROM student_embeddings e
        JOIN students s ON e.student_id = s.id
    """)
    rows = c.fetchall()
    conn.close()

    embeddings = [np.frombuffer(r["vector"], dtype=np.float32) for r in rows]
    student_ids = [r["student_id"] for r in rows]
    meta = {r["student_id"]: {"roll_no": r["roll_no"], "name": r["name"], "branch": r["branch"]} for r in rows}

    known_embs = np.asarray(embeddings, dtype=np.float32)
    known_ids = np.asarray(student_ids)

    print(f"Loaded {len(known_ids)} embeddings across {len(meta)} registered students:")
    for sid, info in meta.items():
        print(f"  - ID {sid}: {info['name']} ({info['roll_no']} • {info['branch']})")

    images_to_test = [
        ("Hostel Group Photo", "test_images/user_group_hostel.jpg", "user_group_hostel_predicted.jpg", 0.36),
        ("Stage / Auditorium Group Photo", "test_images/user_group_stage.png", "user_group_stage_predicted.jpg", 0.35)
    ]

    os.makedirs("annotated_samples", exist_ok=True)
    artifact_dir = r"C:\Users\Md Dilnawaz Ahmad\.gemini\antigravity\brain\5658b065-8074-4609-be07-2656bf4d17f5"

    results = []

    for label, img_path, out_filename, threshold in images_to_test:
        print(f"\n=======================================================")
        print(f"Processing: {label} ({img_path})")
        print(f"=======================================================")
        
        img = cv2.imread(img_path)
        if img is None:
            print(f"Error: Could not read {img_path}")
            continue

        h, w = img.shape[:2]
        print(f"Image Resolution: {w}x{h}")

        # Run face recognition
        dets, annotated_b64 = engine.recognize_faces_in_image(
            img,
            known_embeddings=known_embs,
            known_student_ids=known_ids,
            id_meta_map=meta,
            threshold=threshold,
            draw_annotations=True
        )

        out_path = os.path.join("annotated_samples", out_filename)
        if annotated_b64:
            img_bytes = base64.b64decode(annotated_b64.split(",")[-1])
            with open(out_path, "wb") as f:
                f.write(img_bytes)
            
            # Also copy to artifact directory for display
            artifact_img_path = os.path.join(artifact_dir, out_filename)
            shutil.copy(out_path, artifact_img_path)
            print(f"Saved annotated image to: {out_path} and {artifact_img_path}")

        matched = [d for d in dets if d["is_matched"]]
        unknowns = [d for d in dets if not d["is_matched"]]

        print(f"Total Faces Detected: {len(dets)}")
        print(f"Identified Enrolled Students ({len(matched)}):")
        for m in sorted(matched, key=lambda x: x["score"], reverse=True):
            print(f"  [MATCH] {m['name']} ({m['roll_no']}) - Confidence: {m['score']*100:.1f}%")

        print(f"Unknown / Unenrolled Faces ({len(unknowns)}):")
        for u in unknowns[:5]:
            print(f"  [UNKNOWN] at {u['bbox']} - Best similarity: {u['score']*100:.1f}% (< {threshold*100:.0f}%)")
        if len(unknowns) > 5:
            print(f"  ... and {len(unknowns) - 5} more unknown faces.")

        results.append({
            "label": label,
            "out_filename": out_filename,
            "artifact_path": os.path.join(artifact_dir, out_filename),
            "total_faces": len(dets),
            "matched": matched,
            "unknowns": unknowns
        })

    return results

if __name__ == "__main__":
    run_recognition()
