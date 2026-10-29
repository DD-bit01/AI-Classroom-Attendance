import cv2
import numpy as np
import base64
import os
from insightface.utils.face_align import norm_crop
from face_engine import get_face_engine

def run():
    engine = get_face_engine()

    def get_primary_face_emb(img):
        h, w = img.shape[:2]
        if max(h, w) > 1200:
            scale = 1200 / max(h, w)
            img = cv2.resize(img, (int(w * scale), int(h * scale)))
            h, w = img.shape[:2]
        engine.detector.setInputSize((w, h))
        _, faces = engine.detector.detect(img)
        if faces is None or len(faces) == 0:
            return None
        faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
        f = faces[0]
        lmks = f[4:14].reshape(5, 2).astype(np.float32)
        aligned = norm_crop(img, lmks, image_size=112)
        emb = engine.recognizer.get_feat(aligned).flatten()
        return emb / (np.linalg.norm(emb) + 1e-10)

    actors = [
        ('Robert Downey Jr', 'robert_downey_jr.jpg'),
        ('Tom Cruise', 'tom_cruise.jpg'),
        ('Brad Pitt', 'brad_pitt.jpg'),
        ('Leonardo DiCaprio', 'leonardo_dicaprio.jpg')
    ]

    embs = []
    valid_actors = []
    for idx, (n, p) in enumerate(actors, 1):
        if not os.path.exists(p):
            continue
        img = cv2.imread(p)
        emb = get_primary_face_emb(img)
        if emb is not None:
            embs.append(emb)
            valid_actors.append((idx, n, p))

    known_embs = np.asarray(embs, dtype=np.float32)
    known_ids = np.array([a[0] for a in valid_actors])
    meta = {a[0]: {'name': a[1], 'roll_no': f'ACTOR-{a[0]}'} for a in valid_actors}

    os.makedirs('annotated_samples', exist_ok=True)

    grp = cv2.imread('avengers_cast_group.jpg')
    if grp is not None:
        h, w = grp.shape[:2]
        if max(h, w) > 1400:
            scale = 1400 / max(h, w)
            grp = cv2.resize(grp, (int(w * scale), int(h * scale)))

        dets, annotated_b64 = engine.recognize_faces_in_image(
            grp, known_embs, known_ids, meta, threshold=0.34, draw_annotations=True
        )
        print(f"Avengers Cast: {len(dets)} faces detected.")
        for d in dets:
            if d['is_matched']:
                score_pct = d['score'] * 100
                print(f"Matched {d['name']} with confidence {score_pct:.1f}%")

        if annotated_b64:
            with open('annotated_samples/actors_avengers_annotated.jpg', 'wb') as f:
                f.write(base64.b64decode(annotated_b64.split(',')[-1]))
            print("Saved annotated_samples/actors_avengers_annotated.jpg")

    # Also generate a montage of actor individual predictions
    montage_tiles = []
    for idx, n, p in valid_actors:
        img = cv2.imread(p)
        dets, ann_b64 = engine.recognize_faces_in_image(
            img, known_embs, known_ids, meta, threshold=0.35, draw_annotations=True
        )
        if ann_b64:
            ann_bytes = base64.b64decode(ann_b64.split(',')[-1])
            out_p = f"annotated_samples/actor_{idx}_{n.lower().replace(' ', '_')}.jpg"
            with open(out_p, 'wb') as f:
                f.write(ann_bytes)
            print(f"Saved {out_p}")

if __name__ == '__main__':
    run()
