
import cv2
from pathlib import Path
from insightface.app import FaceAnalysis

IMAGE_DIR=Path("test_images")
IMAGE_FILES=[
    "grp_pankaj_bday.jpeg",
    "grp_pic_2_person.jpeg",
    "grp_pic_with_kids.jpeg"
]
ROTATIONS=[0,90,180,270]

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
    return image.copy()

def map_box_back(box,angle,width,height):
    x1,y1,x2,y2=box

    if angle==90:
        return [y1,height-x2,y2,height-x1]
    if angle==180:
        return [width-x2,height-y2,width-x1,height-y1]
    if angle==270:
        return [width-y2,x1,width-y1,x2]

    return [x1,y1,x2,y2]

for filename in IMAGE_FILES:
    path=IMAGE_DIR/filename
    image=cv2.imread(str(path))

    if image is None:
        print(f"Could not read: {path}")
        continue

    height,width=image.shape[:2]
    results=[]

    print(f"\n{filename}")

    for angle in ROTATIONS:
        rotated=rotate_image(image,angle)
        faces=app.get(rotated)

        detections=[]
        for face in faces:
            box=map_box_back(
                face.bbox,angle,width,height
            )
            detections.append({
                "box":box,
                "score":float(face.det_score)
            })

        score_sum=sum(d["score"] for d in detections)

        results.append({
            "angle":angle,
            "detections":detections,
            "count":len(detections),
            "score_sum":score_sum
        })

        print(
            f"  Rotation {angle}: "
            f"{len(detections)} face(s)"
        )

    # Prefer the rotation with the most faces.
    # Use total confidence to break ties.
    best=max(
        results,
        key=lambda r:(r["count"],r["score_sum"])
    )

    print(
        f"Selected rotation: {best['angle']} degrees"
    )
    print(f"Final face count: {best['count']}")

    output=image.copy()

    for i,detection in enumerate(best["detections"],1):
        x1,y1,x2,y2=[
            int(round(v)) for v in detection["box"]
        ]

        x1=max(0,min(x1,width-1))
        x2=max(0,min(x2,width-1))
        y1=max(0,min(y1,height-1))
        y2=max(0,min(y2,height-1))

        cv2.rectangle(
            output,(x1,y1),(x2,y2),(0,255,0),2
        )
        cv2.putText(
            output,f"Face {i}",
            (x1,max(20,y1-8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,(0,255,0),2
        )

   
    cv2.putText(
        output,
        f"Faces: {best['count']} | Rotation: {best['angle']}",
        (10,30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,(0,255,255),2
    )

    # Resize preview to fit the screen
    max_width=1000
    max_height=700

    scale=min(
        max_width/width,
        max_height/height,
        1.0
    )

    if scale<1.0:
        preview=cv2.resize(
            output,
            (int(width*scale),int(height*scale)),
            interpolation=cv2.INTER_AREA
        )
    else:
        preview=output

    cv2.namedWindow(filename,cv2.WINDOW_NORMAL)
    cv2.resizeWindow(
        filename,
        preview.shape[1],
        preview.shape[0]
    )
    cv2.imshow(filename,preview)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
