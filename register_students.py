
import cv2
import numpy as np
from pathlib import Path
from insightface.model_zoo import get_model
from insightface.utils.face_align import norm_crop

ROOT=Path(__file__).resolve().parent
PHOTO_DIR=ROOT/"student_photos"
YUNET_PATH=ROOT/"models/face_detection_yunet_2026may.onnx"
EMBEDDING_PATH=ROOT/"student_embeddings.npz"

RECOGNITION_MODEL=(
    Path.home()/".insightface/models/buffalo_l/w600k_r50.onnx"
)

detector=cv2.FaceDetectorYN.create(
    str(YUNET_PATH),"",(320,320),0.4,0.3,5000
)

recognizer=get_model(
    str(RECOGNITION_MODEL),
    providers=["CPUExecutionProvider"]
)
recognizer.prepare(ctx_id=-1)

embeddings=[]
student_ids=[]
image_paths=[]

for student_dir in sorted(PHOTO_DIR.iterdir()):
    if not student_dir.is_dir():
        continue

    student_id=student_dir.name

    for path in sorted(student_dir.iterdir()):
        if path.suffix.lower() not in {
            ".jpg",".jpeg",".png",".webp"
        }:
            continue

        image=cv2.imread(str(path))

        if image is None:
            print("Cannot read:",path)
            continue

        h,w=image.shape[:2]
        detector.setInputSize((w,h))
        _,faces=detector.detect(image)

        if faces is None or len(faces)!=1:
            count=0 if faces is None else len(faces)
            print(f"SKIPPED {path.name}: detected {count} faces")
            continue

        face=faces[0]

        # YuNet landmarks: five (x,y) points.
        landmarks=face[4:14].reshape(5,2).astype(np.float32)

        aligned=norm_crop(image,landmarks,image_size=112)
        embedding=recognizer.get_feat(aligned).flatten()

        # L2 normalization
        embedding=embedding/(np.linalg.norm(embedding)+1e-10)

        embeddings.append(embedding)
        student_ids.append(student_id)
        image_paths.append(str(path.relative_to(ROOT)))

        print("Registered:",student_id,"<-",path.name)

if not embeddings:
    raise RuntimeError(
        "No embeddings generated. Check photos, model paths, and detections."
    )

np.savez_compressed(
    EMBEDDING_PATH,
    embeddings=np.asarray(embeddings,dtype=np.float32),
    student_ids=np.asarray(student_ids),
    image_paths=np.asarray(image_paths)
)

print(f"\nSaved {len(embeddings)} embeddings to {EMBEDDING_PATH}")
print("Registered students:",len(set(student_ids)))
