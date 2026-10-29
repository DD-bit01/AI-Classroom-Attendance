import os
import cv2
import numpy as np
import database as db
from face_engine import get_face_engine

def generate_annotated_images():
    output_dir = "annotated_samples"
    os.makedirs(output_dir, exist_ok=True)

    engine = get_face_engine()
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT e.student_id, s.roll_no, s.name, e.vector
        FROM student_embeddings e
        JOIN students s ON e.student_id = s.id
    """)
    rows = cursor.fetchall()
    conn.close()

    embeddings = [np.frombuffer(r["vector"], dtype=np.float32) for r in rows]
    student_ids = [r["student_id"] for r in rows]
    metadata = {r["student_id"]: {"roll_no": r["roll_no"], "name": r["name"]} for r in rows}
    
    known_embs = np.asarray(embeddings, dtype=np.float32)
    known_ids = np.asarray(student_ids)

    test_imgs = [
        ("class_room_image.jpeg", "classroom_annotated.jpg", 0.36),
        ("grp_bday.jpeg", "grp_bday_annotated.jpg", 0.38),
        ("grp_pankaj_bday.jpeg", "grp_pankaj_annotated.jpg", 0.38),
        ("grp_pic_2_person.jpeg", "grp_2person_annotated.jpg", 0.38),
        ("grp_pic_with_kids.jpeg", "grp_kids_annotated.jpg", 0.38),
    ]

    results = {}
    for filename, out_name, thresh in test_imgs:
        path = os.path.join("test_images", filename)
        if not os.path.exists(path):
            continue
        img = cv2.imread(path)
        if img is None:
            continue

        dets, annotated_b64 = engine.recognize_faces_in_image(
            img, known_embs, known_ids, metadata, threshold=thresh, draw_annotations=True
        )

        out_path = os.path.join(output_dir, out_name)
        # Decode annotated b64 back to image or draw on copy
        if annotated_b64:
            import base64
            img_data = base64.b64decode(annotated_b64.split(",")[-1])
            with open(out_path, "wb") as f:
                f.write(img_data)
        else:
            cv2.imwrite(out_path, img)

        matched = [d for d in dets if d["is_matched"]]
        print(f"Generated {out_name}: {len(dets)} detected, {len(matched)} matched.")
        results[out_name] = {
            "total": len(dets),
            "matched": [(m["name"], m["score"]) for m in matched],
            "orig_path": path,
            "annotated_path": out_path
        }
    return results

if __name__ == "__main__":
    generate_annotated_images()
