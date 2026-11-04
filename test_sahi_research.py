"""
AURA Scientific Research Benchmark:
Standard Baseline Pipeline vs. SAHI + Super-Resolution Enhancement
Evaluates detection count, true matches, and confidence gain on classroom imagery.
"""

import cv2
import time
import numpy as np
from pathlib import Path
from face_engine import get_face_engine
from sahi_face_engine import SAHIFaceEngine
import database as db

ROOT = Path('.').resolve()
OUTPUT_DIR = ROOT / 'annotated_samples'
OUTPUT_DIR.mkdir(exist_ok=True)

def run_research_benchmark(image_path: str = 'test_images/industry_class_photo.jpeg'):
    if not Path(image_path).exists():
        print(f"[!] Target image '{image_path}' not found!")
        return

    print("=" * 70)
    print(" AURA AI RESEARCH BENCHMARK: SAHI + ENHANCEMENT EVALUATION")
    print("=" * 70)

    img = cv2.imread(image_path)
    img_h, img_w = img.shape[:2]
    print(f"Target Image       : {image_path}")
    print(f"Native Resolution  : {img_w} x {img_h} ({round((img_w * img_h) / 1e6, 2)} Megapixels)")

    # 1. Fetch registered embeddings
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

    print(f"Enrolled Students  : {len(meta)} students ({len(known_ids)} reference vectors)")
    print("-" * 70)

    # ================= EXPERIMENT A: BASELINE ================= #
    print("\n[EXPERIMENT A] Running Baseline (Standard Downscale + Standard ArcFace)...")
    base_engine = get_face_engine()
    t0 = time.time()
    base_dets, _ = base_engine.recognize_faces_in_image(
        img,
        known_embeddings=known_embs,
        known_student_ids=known_ids,
        id_meta_map=meta,
        threshold=0.36,
        draw_annotations=False
    )
    t_base = time.time() - t0
    base_matched = [d for d in base_dets if d["is_matched"]]
    base_unknowns = [d for d in base_dets if not d["is_matched"]]

    print(f"  -> Execution Time   : {t_base:.3f} seconds")
    print(f"  -> Faces Detected   : {len(base_dets)}")
    print(f"  -> Students Matched : {len(base_matched)}")
    print(f"  -> Unknown Faces    : {len(base_unknowns)}")

    # ================= EXPERIMENT B: SAHI + ENHANCEMENT ================= #
    print("\n[EXPERIMENT B] Running SAHI (Sliced Overlapping Tiles) + Adaptive Face Enhancement...")
    sahi_engine = SAHIFaceEngine(slice_size=(640, 640), overlap_ratio=0.25)
    t1 = time.time()
    sahi_dets = sahi_engine.recognize_with_sahi(
        img,
        known_embeddings=known_embs,
        known_student_ids=known_ids,
        id_meta_map=meta,
        threshold=0.34
    )
    t_sahi = time.time() - t1
    sahi_matched = [d for d in sahi_dets if d["is_matched"]]
    sahi_unknowns = [d for d in sahi_dets if not d["is_matched"]]

    print(f"  -> Execution Time   : {t_sahi:.3f} seconds")
    print(f"  -> Faces Detected   : {len(sahi_dets)}")
    print(f"  -> Students Matched : {len(sahi_matched)}")
    print(f"  -> Unknown Faces    : {len(sahi_unknowns)}")

    # Print Identified students comparison
    print("\n" + "=" * 70)
    print(" RECOGNITION COMPARISON SUMMARY")
    print("=" * 70)
    print(f"{'Metric':<25} | {'Baseline':<18} | {'SAHI + Enhancement':<22}")
    print("-" * 70)
    print(f"{'Detected Faces':<25} | {len(base_dets):<18} | {len(sahi_dets):<22}")
    print(f"{'Identified Students':<25} | {len(base_matched):<18} | {len(sahi_matched):<22}")
    print(f"{'Unknown Bounding Boxes':<25} | {len(base_unknowns):<18} | {len(sahi_unknowns):<22}")
    print(f"{'Inference Latency':<25} | {t_base:.2f}s{'':<13} | {t_sahi:.2f}s{'':<17}")

    print("\nIdentified Students via SAHI Pipeline:")
    sahi_matched.sort(key=lambda x: x["score"], reverse=True)
    for idx, m in enumerate(sahi_matched, start=1):
        print(f"  {idx:02d}. {m['name']} ({m['roll_no']}) -> Confidence: {m['score']*100:.1f}%")

    # Render SAHI visual output
    annotated = img.copy()
    for det in sahi_dets:
        x, y, bw, bh = det["bbox"]
        if det["is_matched"]:
            color = (60, 220, 80) # Emerald Green
            label = f"{det['name']} ({int(det['score']*100)}%)"
            cv2.rectangle(annotated, (x, y), (x + bw, y + bh), color, 2)
            cv2.rectangle(annotated, (x, max(0, y - 20)), (x + bw, y), color, -1)
            cv2.putText(annotated, label, (x + 3, max(12, y - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 0, 0), 1, cv2.LINE_AA)
        else:
            color = (255, 180, 0) # Cyan/Sky-Blue clean outline
            cv2.rectangle(annotated, (x, y), (x + bw, y + bh), color, 1)

    out_path = OUTPUT_DIR / "research_sahi_benchmark.jpeg"
    cv2.imwrite(str(out_path), annotated)
    print(f"\n[Artifact Generated] Visual comparison saved to: {out_path.relative_to(ROOT)}")
    print("=" * 70)

if __name__ == '__main__':
    run_research_benchmark()
