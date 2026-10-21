
import cv2
from pathlib import Path
from insightface.app import FaceAnalysis

MODEL_DIR=Path("test_images")
PREVIEW_WIDTH=900
PREVIEW_HEIGHT=650
IOU_THRESHOLD=0.40

app=FaceAnalysis(
    name="buffalo_l",
    allowed_modules=["detection"],
    providers=["CPUExecutionProvider"]
)
app.prepare(ctx_id=-1,det_size=(640,640))


def rotate_image(image,angle):
    if angle==90:
        return cv2.rotate(image,cv2.ROTATE_90_CLOCKWISE)
    if angle==180:
        return cv2.rotate(image,cv2.ROTATE_180)
    if angle==270:
        return cv2.rotate(image,cv2.ROTATE_90_COUNTERCLOCKWISE)
    return image


def map_box_back(box,angle,W,H):
    x1,y1,x2,y2=map(float,box)

    if angle==90:
        return [y1,H-x2,y2,H-x1]
    if angle==180:
        return [W-x2,H-y2,W-x1,H-y1]
    if angle==270:
        return [W-y2,x1,W-y1,x2]

    return [x1,y1,x2,y2]


def iou(box1,box2):
    x1=max(box1[0],box2[0])
    y1=max(box1[1],box2[1])
    x2=min(box1[2],box2[2])
    y2=min(box1[3],box2[3])

    intersection=max(0,x2-x1)*max(0,y2-y1)

    area1=max(0,box1[2]-box1[0])*max(0,box1[3]-box1[1])
    area2=max(0,box2[2]-box2[0])*max(0,box2[3]-box2[1])
    union=area1+area2-intersection

    return intersection/union if union>0 else 0


def merge_duplicates(detections):
    # Highest-confidence detections are considered first.
    detections.sort(key=lambda item:item[1],reverse=True)
    kept=[]

    for box,score,angle in detections:
        duplicate=False

        for old_box,old_score,old_angle in kept:
            if iou(box,old_box)>=IOU_THRESHOLD:
                duplicate=True
                break

        if not duplicate:
            kept.append((box,score,angle))

    return kept


extensions={".jpg",".jpeg",".png",".bmp",".webp"}
images=sorted(
    p for p in MODEL_DIR.iterdir()
    if p.suffix.lower() in extensions
)

if not images:
    raise FileNotFoundError("No images found in test_images/")

for path in images:
    original=cv2.imread(str(path))

    if original is None:
        print("Cannot read:",path.name)
        continue

    H,W=original.shape[:2]
    all_detections=[]

    print(f"\n{path.name}")

    for angle in [0,90,180,270]:
        rotated=rotate_image(original,angle)
        faces=app.get(rotated)

        print(f"  Rotation {angle}: {len(faces)} face(s)")

        for face in faces:
            box=map_box_back(face.bbox,angle,W,H)

            x1=max(0,min(W-1,box[0]))
            y1=max(0,min(H-1,box[1]))
            x2=max(0,min(W,box[2]))
            y2=max(0,min(H,box[3]))

            if x2>x1 and y2>y1:
                all_detections.append(
                    ([x1,y1,x2,y2],float(face.det_score),angle)
                )

    final_faces=merge_duplicates(all_detections)
    print(f"  After merging: {len(final_faces)} face(s)")

    preview=original.copy()

    for box,score,angle in final_faces:
        x1,y1,x2,y2=map(int,box)
        cv2.rectangle(preview,(x1,y1),(x2,y2),(0,255,0),2)

    scale=min(PREVIEW_WIDTH/W,PREVIEW_HEIGHT/H,1.0)
    preview=cv2.resize(
        preview,
        (max(1,int(W*scale)),max(1,int(H*scale)))
    )

    cv2.namedWindow("SCRFD Rotation Test",cv2.WINDOW_NORMAL)
    cv2.resizeWindow(
        "SCRFD Rotation Test",preview.shape[1],preview.shape[0]
    )
    cv2.imshow("SCRFD Rotation Test",preview)

    print("Click the image window and press a key for the next photo.")
    cv2.waitKey(0)
    cv2.destroyWindow("SCRFD Rotation Test")

cv2.destroyAllWindows()
