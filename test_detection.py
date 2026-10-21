
import cv2
from pathlib import Path

MODEL_PATH="models/face_detection_yunet_2026may.onnx"
IMAGE_DIR=Path("test_images")

CONFIDENCE=0.4
NMS_THRESHOLD=0.3
PREVIEW_WIDTH=900
PREVIEW_HEIGHT=650

detector=cv2.FaceDetectorYN.create(
    MODEL_PATH,
    "",
    (320,320),
    CONFIDENCE,
    NMS_THRESHOLD,
    5000
)

extensions={".jpg",".jpeg",".png",".bmp",".webp"}

images=sorted(
    p for p in IMAGE_DIR.iterdir()
    if p.suffix.lower() in extensions
)

if not images:
    raise FileNotFoundError("No images found in test_images/")

for path in images:
    image=cv2.imread(str(path))

    if image is None:
        print("Cannot read:",path.name)
        continue

    h,w=image.shape[:2]
    detector.setInputSize((w,h))

    _,faces=detector.detect(image)
    count=0 if faces is None else len(faces)

    print(f"{path.name}: {count} face(s) detected")

    if faces is not None:
        for face in faces:
            x,y,bw,bh=map(int,face[:4])
            cv2.rectangle(
                image,(x,y),(x+bw,y+bh),(0,255,0),2
            )

    scale=min(
        PREVIEW_WIDTH/w,
        PREVIEW_HEIGHT/h,
        1.0
    )

    preview=cv2.resize(
        image,
        (max(1,int(w*scale)),max(1,int(h*scale)))
    )

    cv2.namedWindow("Face Detection",cv2.WINDOW_NORMAL)
    cv2.resizeWindow(
        "Face Detection",preview.shape[1],preview.shape[0]
    )
    cv2.imshow("Face Detection",preview)

    print("Press any key to view the next image.")
    cv2.waitKey(0)

cv2.destroyAllWindows()
