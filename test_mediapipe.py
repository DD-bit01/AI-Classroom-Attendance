
import cv2
import mediapipe as mp
from pathlib import Path

IMAGE_DIR=Path("test_images")
PREVIEW_WIDTH=900
PREVIEW_HEIGHT=650

IMAGE_FILES=[
    "grp_pankaj_bday.jpeg",
    "grp_pic_2_person.jpeg",
    "grp_pic_with_kids.jpeg"
]

mp_face_detection=mp.solutions.face_detection

with mp_face_detection.FaceDetection(
    model_selection=1,
    min_detection_confidence=0.5
) as detector:

    for filename in IMAGE_FILES:
        path=IMAGE_DIR/filename
        image=cv2.imread(str(path))

        if image is None:
            print(f"Cannot read: {filename}")
            continue

        height,width=image.shape[:2]
        rgb=cv2.cvtColor(image,cv2.COLOR_BGR2RGB)
        results=detector.process(rgb)

        faces=results.detections or []
        print(f"{filename}: {len(faces)} face(s) detected")

        output=image.copy()

        for face in faces:
            bbox=face.location_data.relative_bounding_box

            x1=max(0,int(bbox.xmin*width))
            y1=max(0,int(bbox.ymin*height))
            x2=min(width,int((bbox.xmin+bbox.width)*width))
            y2=min(height,int((bbox.ymin+bbox.height)*height))

            cv2.rectangle(
                output,(x1,y1),(x2,y2),(0,255,0),2
            )

        scale=min(
            PREVIEW_WIDTH/width,
            PREVIEW_HEIGHT/height,
            1.0
        )

        preview=cv2.resize(
            output,
            (max(1,int(width*scale)),max(1,int(height*scale))),
            interpolation=cv2.INTER_AREA
        )

        cv2.namedWindow(filename,cv2.WINDOW_NORMAL)
        cv2.resizeWindow(
            filename,preview.shape[1],preview.shape[0]
        )
        cv2.imshow(filename,preview)

        print("Press any key to view the next image.")
        cv2.waitKey(0)
        cv2.destroyAllWindows()
