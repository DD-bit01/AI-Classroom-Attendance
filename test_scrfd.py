
import cv2
from pathlib import Path
from insightface.app import FaceAnalysis

IMAGE_DIR=Path("test_images")
PREVIEW_WIDTH=900
PREVIEW_HEIGHT=650

# CPU inference: works without an NVIDIA GPU
app=FaceAnalysis(
    name="buffalo_l",
    allowed_modules=["detection"],
    providers=["CPUExecutionProvider"]
)
app.prepare(ctx_id=-1,det_size=(640,640))

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

    faces=app.get(image)
    print(f"{path.name}: {len(faces)} face(s) detected")

    for face in faces:
        x1,y1,x2,y2=face.bbox.astype(int)
        cv2.rectangle(
            image,(x1,y1),(x2,y2),(0,255,0),2
        )

    h,w=image.shape[:2]
    scale=min(PREVIEW_WIDTH/w,PREVIEW_HEIGHT/h,1.0)
    preview=cv2.resize(
        image,
        (max(1,int(w*scale)),max(1,int(h*scale)))
    )

    cv2.namedWindow("SCRFD Face Detection",cv2.WINDOW_NORMAL)
    cv2.resizeWindow(
        "SCRFD Face Detection",
        preview.shape[1],preview.shape[0]
    )
    cv2.imshow("SCRFD Face Detection",preview)
    cv2.waitKey(0)

cv2.destroyAllWindows()

