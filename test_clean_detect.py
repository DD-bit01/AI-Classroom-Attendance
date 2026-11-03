import cv2
import sys
import os
from pathlib import Path
from face_engine import get_face_engine
import database as db

def test_image_visualize(image_path: str, output_path: str = None, session_id: int = None):
    if not os.path.exists(image_path):
        print(f"Error: File not found at '{image_path}'")
        return

    img = cv2.imread(image_path)
    if img is None:
        print(f"Error: Unable to read image '{image_path}'")
        return

    print(f"\n[1/4] Loaded image: {image_path} (Size: {img.shape[1]}x{img.shape[0]})")
    
    # 1. Fetch registered embeddings if session_id is provided or take first active session
    known_emb, known_ids, id_meta = None, None, None
    if session_id:
        known_emb, known_ids, id_meta = db.get_registered_embeddings_for_session(session_id)
    else:
        sessions = db.get_all_sessions()
        if sessions:
            first_sid = sessions[0]["id"]
            known_emb, known_ids, id_meta = db.get_registered_embeddings_for_session(first_sid)
            print(f"[2/4] Loaded biometric profile from Session #{first_sid} ({sessions[0]['course_code']} - {sessions[0]['title']})")
        else:
            print("[2/4] No active sessions found; running in pure detection mode.")

    engine = get_face_engine()

    # 2. Run face detection and recognition
    print("[3/4] Running YuNet face detection & ArcFace embedding...")
    detections, _ = engine.recognize_faces_in_image(
        img,
        known_embeddings=known_emb,
        known_student_ids=known_ids,
        id_meta_map=id_meta,
        threshold=0.38,
        draw_annotations=False
    )

    print(f"[4/4] Successfully detected {len(detections)} real human faces!")

    # 3. Draw clean boxes WITHOUT any "Unknown" labels
    # If a student is recognized, display their Name and Score.
    # If not recognized, draw a clean minimalist bounding box with NO text.
    annotated = img.copy()

    for idx, det in enumerate(detections, start=1):
        x, y, bw, bh = det["bbox"]
        is_matched = det["is_matched"]
        name = det["name"]
        score = det["score"]

        if is_matched:
            # Recognized student: Emerald Green box + Name badge
            box_color = (60, 220, 80)
            cv2.rectangle(annotated, (x, y), (x + bw, y + bh), box_color, 2)
            
            # Corner accents
            c_len = max(8, min(16, int(bw * 0.18)))
            cv2.line(annotated, (x, y), (x + c_len, y), (255, 255, 255), 2)
            cv2.line(annotated, (x, y), (x, y + c_len), (255, 255, 255), 2)
            cv2.line(annotated, (x + bw, y), (x + bw - c_len, y), (255, 255, 255), 2)
            cv2.line(annotated, (x + bw, y), (x + bw, y + c_len), (255, 255, 255), 2)

            # Name pill badge
            label = f"{name} ({int(score * 100)}%)"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.45
            (tw, th), _ = cv2.getTextSize(label, font, font_scale, 1)
            badge_h = th + 8
            badge_w = tw + 12
            badge_y = max(badge_h, y - 4)
            cv2.rectangle(annotated, (x, badge_y - badge_h), (x + badge_w, badge_y), (10, 40, 20), -1)
            cv2.rectangle(annotated, (x, badge_y - badge_h), (x + badge_w, badge_y), box_color, 1)
            cv2.putText(annotated, label, (x + 6, badge_y - 4), font, font_scale, (160, 255, 180), 1, cv2.LINE_AA)
            print(f"  [Face {idx}] RECOGNIZED: {name} (Confidence: {int(score * 100)}%) at bbox [{x}, {y}, {bw}, {bh}]")
        else:
            # Unmatched face: Clean Cyan/Sky-Blue box, ABSOLUTELY NO TEXT
            box_color = (255, 191, 0) # Amber / Sky Blue (0, 200, 255) in BGR
            box_color = (255, 180, 0)
            cv2.rectangle(annotated, (x, y), (x + bw, y + bh), box_color, 2)
            
            # Corner accents for a high-tech clean look
            c_len = max(6, min(14, int(bw * 0.20)))
            cv2.line(annotated, (x, y), (x + c_len, y), (255, 255, 255), 2)
            cv2.line(annotated, (x, y), (x, y + c_len), (255, 255, 255), 2)
            cv2.line(annotated, (x + bw, y), (x + bw - c_len, y), (255, 255, 255), 2)
            cv2.line(annotated, (x + bw, y), (x + bw, y + c_len), (255, 255, 255), 2)
            cv2.line(annotated, (x, y + bh), (x + c_len, y + bh), (255, 255, 255), 2)
            cv2.line(annotated, (x, y + bh), (x, y + bh - c_len), (255, 255, 255), 2)
            cv2.line(annotated, (x + bw, y + bh), (x + bw - c_len, y + bh), (255, 255, 255), 2)
            cv2.line(annotated, (x + bw, y + bh), (x + bw, y + bh - c_len), (255, 255, 255), 2)
            print(f"  [Face {idx}] Detected face (clean box drawn) at bbox [{x}, {y}, {bw}, {bh}]")

    # 4. Save output
    if not output_path:
        base, ext = os.path.splitext(image_path)
        # Ensure valid image extension for OpenCV imwrite
        if ext.lower() not in ['.jpg', '.jpeg', '.png', '.webp', '.bmp']:
            ext = '.jpg'
        output_path = f"{base}_clean_detected{ext}"
    else:
        # Check if output_path has an extension; if not, append .jpg
        _, out_ext = os.path.splitext(output_path)
        if out_ext.lower() not in ['.jpg', '.jpeg', '.png', '.webp', '.bmp']:
            output_path += '.jpg'

    # Handle Unicode paths and save safely
    success = False
    try:
        ext = os.path.splitext(output_path)[1]
        if not ext:
            ext = '.jpg'
        is_success, buffer = cv2.imencode(ext, annotated)
        if is_success:
            with open(output_path, "wb") as f:
                f.write(buffer)
            success = True
    except Exception:
        pass

    if not success:
        cv2.imwrite(output_path, annotated)

    print(f"\n--> Saved output image with clean boxes to:\n    {os.path.abspath(output_path)}\n")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        img_arg = sys.argv[1]
        out_arg = sys.argv[2] if len(sys.argv) > 2 else None
        test_image_visualize(img_arg, out_arg)
    else:
        # Default test on sample group image
        sample = "test_images/grp_pic_with_kids.jpeg"
        print(f"Usage: python test_clean_detect.py <path_to_group_photo> [output_path]")
        print(f"No path provided, running on sample: {sample}...\n")
        test_image_visualize(sample)
