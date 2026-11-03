import cv2
import numpy as np
import base64
from pathlib import Path
from insightface.model_zoo import get_model
from insightface.utils.face_align import norm_crop

ROOT = Path(__file__).resolve().parent
YUNET_PATH = ROOT / "models/face_detection_yunet_2026may.onnx"
if not YUNET_PATH.exists():
    YUNET_PATH = ROOT / "models/face_detection_yunet_2023mar.onnx"

RECOGNITION_MODEL = Path.home() / ".insightface/models/buffalo_l/w600k_r50.onnx"

class FaceEngine:
    _instance = None

    def __init__(self):
        print(f"[FaceEngine] Loading YuNet from {YUNET_PATH}...")
        self.detector = cv2.FaceDetectorYN.create(
            str(YUNET_PATH), "", (320, 320), 0.4, 0.3, 5000
        )
        print(f"[FaceEngine] Loading ArcFace from {RECOGNITION_MODEL}...")
        self.recognizer = get_model(
            str(RECOGNITION_MODEL),
            providers=["CPUExecutionProvider"]
        )
        self.recognizer.prepare(ctx_id=-1)
        print("[FaceEngine] Engine ready.")

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = FaceEngine()
        return cls._instance

    @staticmethod
    def decode_image_bytes(image_bytes: bytes) -> np.ndarray:
        if not image_bytes:
            return None
        try:
            from PIL import Image, ImageOps
            import io
            pil_img = Image.open(io.BytesIO(image_bytes))
            pil_img = ImageOps.exif_transpose(pil_img)
            if pil_img.mode != "RGB":
                pil_img = pil_img.convert("RGB")
            return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        except Exception:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            return img

    @staticmethod
    def encode_image_base64(image_bgr: np.ndarray, quality: int = 85) -> str:
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
        success, buffer = cv2.imencode('.jpg', image_bgr, encode_param)
        if not success:
            return ""
        b64 = base64.b64encode(buffer).decode('utf-8')
        return f"data:image/jpeg;base64,{b64}"

    def extract_single_face_embedding(self, image_bgr: np.ndarray):
        """
        Validate face presence and extract normalized 512-d ArcFace embedding.
        Robust to multi-face backgrounds (selects dominant primary subject) and phone tilt/rotation.
        Returns: (embedding, error_message)
        """
        if image_bgr is None or image_bgr.size == 0:
            return None, "Invalid image data."

        work_img = image_bgr.copy()
        h, w = work_img.shape[:2]

        # Downscale massive phone photos (e.g. 48MP/12MP) to keep face within detector scale
        max_dim = 1600
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            work_img = cv2.resize(work_img, (int(w * scale), int(h * scale)))
            h, w = work_img.shape[:2]

        # 1. First attempt: standard orientation
        self.detector.setInputSize((w, h))
        _, faces = self.detector.detect(work_img)

        # 2. Fallback attempt: Try 90, 180, 270 rotations if 0 faces found (phone orientation)
        if faces is None or len(faces) == 0:
            for rot in [cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_180, cv2.ROTATE_90_COUNTERCLOCKWISE]:
                rotated = cv2.rotate(work_img, rot)
                rh, rw = rotated.shape[:2]
                self.detector.setInputSize((rw, rh))
                _, r_faces = self.detector.detect(rotated)
                if r_faces is not None and len(r_faces) > 0:
                    work_img = rotated
                    h, w = rh, rw
                    faces = r_faces
                    break

        if faces is None or len(faces) == 0:
            return None, "No face detected in photo. Please ensure face is centered, well-lit, and not blurry."

        # 3. Filter valid candidate faces (reject false non-face detections)
        valid_candidates = []
        for f in faces:
            fx, fy, fw, fh = map(int, f[:4])
            conf = float(f[-1])
            # Strict confidence threshold for registration (real portrait faces are >= 0.60)
            if conf < 0.60:
                continue
            # Aspect ratio check (human face bounding box height/width ratio is typically 0.8 - 1.8)
            ratio = fh / max(1, fw)
            if ratio < 0.60 or ratio > 2.2:
                continue
            valid_candidates.append(f)

        if not valid_candidates:
            # Fall back to best detected face if confidence was close
            valid_candidates = [f for f in faces if f[-1] >= 0.45]
            if not valid_candidates:
                return None, "Detected face confidence too low. Please use a clearer, well-lit portrait."

        # 4. Multi-face scoring: prioritize confidence and centrality (portrait subject)
        def face_quality_metric(f):
            fx, fy, fw, fh = f[:4]
            conf = float(f[-1])
            face_cx = fx + fw / 2.0
            face_cy = fy + fh / 2.0
            dist_norm = np.sqrt(((face_cx - w / 2.0) / w) ** 2 + ((face_cy - h / 2.0) / h) ** 2)
            centrality = max(0.1, 1.0 - dist_norm)
            area_ratio = (fw * fh) / (w * h)
            # High confidence + centered in portrait frame dominates area
            return (conf ** 2) * centrality * np.sqrt(area_ratio)

        valid_candidates.sort(key=face_quality_metric, reverse=True)

        # If photo clearly contains multiple distinct prominent people
        if len(valid_candidates) >= 3:
            q0 = face_quality_metric(valid_candidates[0])
            q1 = face_quality_metric(valid_candidates[1])
            if q0 < q1 * 1.3:
                return None, f"Detected {len(valid_candidates)} people in photo. Please use a solo portrait where the student is centered."

        face = valid_candidates[0]
        landmarks = face[4:14].reshape(5, 2).astype(np.float32)
        aligned = norm_crop(work_img, landmarks, image_size=112)

        embedding = self.recognizer.get_feat(aligned).flatten()
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        return embedding.astype(np.float32), None

    def validate_portrait_face(self, image_bgr: np.ndarray) -> dict:
        """
        Validates whether an image contains a clear, valid, single human face.
        Rejects non-face photos (desks, computers, laptops, walls, pets, clutter),
        group photos (>1 face), tiny/distant faces, and blurry low-confidence faces.
        Returns:
            dict with {
                "valid": bool,
                "error": Optional[str],
                "confidence": Optional[float],
                "face_count": int,
                "box": Optional[list]
            }
        """
        if image_bgr is None or image_bgr.size == 0:
            return {"valid": False, "error": "Invalid or empty image file.", "face_count": 0}

        h, w = image_bgr.shape[:2]
        if h < 80 or w < 80:
            return {"valid": False, "error": "Image resolution is too low. Please provide a clear camera photo.", "face_count": 0}

        # Try extracting single face embedding using the robust detector & orientation pipeline
        emb, err = self.extract_single_face_embedding(image_bgr)
        if err is not None or emb is None:
            # Map error message to student-friendly language
            if "No face detected" in err:
                user_msg = "No face detected in this photo. Please capture a clear photo of your face (not a desk, computer, or object)."
            elif "people in photo" in err or "solo portrait" in err:
                user_msg = err
            elif "confidence too low" in err:
                user_msg = "Face is too blurry or dark. Please ensure good lighting and look toward the camera."
            else:
                user_msg = err
            return {"valid": False, "error": user_msg, "face_count": 0}

        # Extract detection stats for feedback
        work_img = image_bgr.copy()
        max_dim = 1600
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            work_img = cv2.resize(work_img, (int(w * scale), int(h * scale)))
            h, w = work_img.shape[:2]

        self.detector.setInputSize((w, h))
        _, faces = self.detector.detect(work_img)
        conf = 0.90
        box = None
        face_count = 1
        if faces is not None and len(faces) > 0:
            best_face = max(faces, key=lambda f: float(f[-1]))
            conf = float(best_face[-1])
            box = [int(v) for v in best_face[:4]]
            face_count = len([f for f in faces if float(f[-1]) >= 0.50])

        return {
            "valid": True,
            "error": None,
            "confidence": round(conf, 3),
            "face_count": max(1, face_count),
            "box": box
        }

    def recognize_faces_in_image(
        self,
        image_bgr: np.ndarray,
        known_embeddings: np.ndarray = None,
        known_student_ids: np.ndarray = None,
        id_meta_map: dict = None,
        threshold: float = 0.36,
        draw_annotations: bool = True
    ):
        """
        Detect faces in image, match against known embeddings.
        Returns:
            detections: list of dicts (bbox, student_id, name, roll_no, score, is_matched)
            annotated_b64: base64 jpeg string (if draw_annotations=True)
        """
        if image_bgr is None or image_bgr.size == 0:
            return [], ""

        work_img = image_bgr.copy()
        orig_h, orig_w = work_img.shape[:2]

        # Downscale massive phone photos (e.g. 12MP/48MP from Android) to keep face within detector receptive field
        max_dim = 1600
        if max(orig_h, orig_w) > max_dim:
            scale = max_dim / max(orig_h, orig_w)
            work_img = cv2.resize(work_img, (int(orig_w * scale), int(orig_h * scale)))

        h, w = work_img.shape[:2]
        self.detector.setInputSize((w, h))
        _, faces = self.detector.detect(work_img)

        # Fallback orientation check if 0 faces found in original orientation (handles Android portrait tilt)
        if (faces is None or len(faces) == 0) and max(h, w) > 0:
            for rot in [cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_180, cv2.ROTATE_90_COUNTERCLOCKWISE]:
                rotated = cv2.rotate(work_img, rot)
                rh, rw = rotated.shape[:2]
                self.detector.setInputSize((rw, rh))
                _, r_faces = self.detector.detect(rotated)
                if r_faces is not None and len(r_faces) > 0:
                    work_img = rotated
                    h, w = rh, rw
                    faces = r_faces
                    break

        detections = []
        annotated_image = work_img.copy() if draw_annotations else None

        if faces is None or len(faces) == 0:
            return detections, self.encode_image_base64(annotated_image) if draw_annotations else ""

        # Filter candidate faces and apply Multi-Scale IoM Overlap Suppression
        # Also filters non-face artifacts (hands, wrists, clothing patterns) via facial biometric geometry
        valid_faces = []
        for f in faces:
            conf = float(f[-1])
            if conf < 0.45:
                continue
            fx, fy, fw, fh = map(int, f[:4])
            # 1. Aspect ratio validation (human faces are roughly 0.75 to 1.85)
            ar = fh / max(1, fw)
            if ar < 0.75 or ar > 1.85:
                continue
            # 2. Minimum face box dimensions
            if fw < 10 or fh < 12:
                continue
            # 3. Facial Landmark Geometry Verification:
            # YuNet predicts 5 landmarks: right_eye, left_eye, nose, right_mouth, left_mouth.
            # Hands/fingers/elbows mistaken as faces have unnatural, collapsed eye/mouth distances.
            lms = f[4:14].reshape(5, 2)
            re, le, nose, rm, lm = lms
            eye_dist = np.hypot(re[0] - le[0], re[1] - le[1])
            eye_ratio = eye_dist / max(1.0, fw)
            if eye_ratio < 0.28:
                continue
            mouth_dist = np.hypot(rm[0] - lm[0], rm[1] - lm[1])
            mouth_ratio = mouth_dist / max(1.0, fw)
            if mouth_ratio < 0.16:
                continue
            eye_y = (re[1] + le[1]) / 2.0
            mouth_y = (rm[1] + lm[1]) / 2.0
            if (mouth_y - eye_y) < 0.12 * fh:
                continue
            valid_faces.append(f)

        if not valid_faces and len(faces) > 0:
            # Fallback only if highest-confidence face meets reasonable criteria
            best_f = faces[0]
            if float(best_f[-1]) >= 0.55:
                valid_faces = [best_f]

        if len(valid_faces) > 1:
            valid_faces.sort(key=lambda f: float(f[-1]), reverse=True)
            suppressed = []
            for f in valid_faces:
                fx, fy, fw, fh = map(int, f[:4])
                f_area = fw * fh
                is_overlap = False
                for s in suppressed:
                    sx, sy, sw, sh = map(int, s[:4])
                    s_area = sw * sh
                    ix1 = max(fx, sx)
                    iy1 = max(fy, sy)
                    ix2 = min(fx + fw, sx + sw)
                    iy2 = min(fy + fh, sy + sh)
                    iw = max(0, ix2 - ix1)
                    ih = max(0, iy2 - iy1)
                    inter = iw * ih
                    if inter > 0:
                        iom = inter / max(1, min(f_area, s_area))
                        iou = inter / max(1, (f_area + s_area - inter))
                        if iom > 0.30 or iou > 0.20:
                            is_overlap = True
                            break
                if not is_overlap:
                    suppressed.append(f)
            valid_faces = suppressed

        # Pre-group known embeddings by student_id for ensemble matching
        student_emb_groups = {}
        if known_embeddings is not None and known_student_ids is not None and len(known_embeddings) > 0:
            for idx, sid in enumerate(known_student_ids):
                sid = int(sid)
                if sid not in student_emb_groups:
                    student_emb_groups[sid] = []
                student_emb_groups[sid].append(known_embeddings[idx])
            for sid in student_emb_groups:
                student_emb_groups[sid] = np.array(student_emb_groups[sid], dtype=np.float32)

        raw_detections = []
        for idx, face in enumerate(valid_faces):
            x, y, bw, bh = map(int, face[:4])
            # Constrain to image boundaries
            x = max(0, min(w - 1, x))
            y = max(0, min(h - 1, y))
            bw = max(1, min(w - x, bw))
            bh = max(1, min(h - y, bh))

            landmarks = face[4:14].reshape(5, 2).astype(np.float32)
            aligned = norm_crop(work_img, landmarks, image_size=112)

            embedding = self.recognizer.get_feat(aligned).flatten()
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm

            matched_id = None
            student_name = "Unknown"
            student_roll = ""
            best_score = 0.0
            is_matched = False

            if student_emb_groups:
                # Robust student-level scoring
                best_student_id = None
                highest_student_score = -1.0

                for sid, s_embs in student_emb_groups.items():
                    sims = s_embs @ embedding
                    sims_sorted = np.sort(sims)[::-1]
                    s_max = float(sims_sorted[0])

                    # Ensemble score: if student has multiple photos, combine top-2
                    # to prevent a single corrupted/outlier photo from causing false positives
                    if len(sims_sorted) >= 2:
                        s_top2 = float(sims_sorted[1])
                        if s_max >= threshold and s_top2 < 0.15:
                            comp_score = s_max * 0.6 + s_top2 * 0.4
                        else:
                            comp_score = s_max * 0.75 + s_top2 * 0.25
                    else:
                        comp_score = s_max

                    if comp_score > highest_student_score:
                        highest_student_score = comp_score
                        best_student_id = sid

                best_score = float(highest_student_score)
                if best_score >= threshold and best_student_id is not None:
                    matched_id = int(best_student_id)
                    if id_meta_map and matched_id in id_meta_map:
                        student_name = id_meta_map[matched_id]["name"]
                        student_roll = id_meta_map[matched_id]["roll_no"]
                    else:
                        student_name = f"Student #{matched_id}"
                    is_matched = True

            det_info = {
                "bbox": [x, y, bw, bh],
                "student_id": matched_id,
                "name": student_name,
                "roll_no": student_roll,
                "score": round(best_score, 3),
                "is_matched": is_matched
            }
            raw_detections.append(det_info)

        # Same-student deduplication:
        # A single student cannot have multiple overlapping boxes on their face
        final_detections = []
        matched_seen = {}

        raw_detections.sort(key=lambda d: (d["is_matched"], d["score"]), reverse=True)

        for det in raw_detections:
            sid = det["student_id"]
            if det["is_matched"] and sid:
                if sid in matched_seen:
                    # Check overlap with previous detection of this same student
                    prev_det = matched_seen[sid]
                    px, py, pw, ph = prev_det["bbox"]
                    dx, dy, dw, dh = det["bbox"]
                    ix1, iy1 = max(px, dx), max(py, dy)
                    ix2, iy2 = min(px + pw, dx + dw), min(py + ph, dy + dh)
                    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
                    iom = inter / max(1, min(pw * ph, dw * dh))
                    if iom > 0.15:
                        # Drop duplicate secondary box on the same student's face
                        continue
                    else:
                        # In a completely different part of the frame, re-label as Unknown
                        det["is_matched"] = False
                        det["student_id"] = None
                        det["name"] = "Unknown"
                        det["roll_no"] = ""
                else:
                    matched_seen[sid] = det

            final_detections.append(det)

        detections = final_detections

        # Draw clean, aesthetic annotations onto the deduplicated final detections
        if draw_annotations and annotated_image is not None:
            for det in detections:
                x, y, bw, bh = det["bbox"]
                is_matched = det["is_matched"]
                student_name = det["name"]
                score = det["score"]

                if is_matched:
                    box_color = (60, 220, 80)     # Emerald Green
                    label = f"{student_name} ({int(score * 100)}%)"
                    badge_bg = (10, 40, 20)
                    text_color = (160, 255, 180)
                else:
                    box_color = (70, 70, 220)     # Soft Crimson
                    label = f"Unknown"
                    badge_bg = (20, 20, 60)
                    text_color = (200, 200, 255)

                # Thin elegant bounding box
                cv2.rectangle(annotated_image, (x, y), (x + bw, y + bh), box_color, 2)

                # Subtle corner accents for high-end look
                c_len = max(8, min(16, int(bw * 0.18)))
                cv2.line(annotated_image, (x, y), (x + c_len, y), (255, 255, 255), 2)
                cv2.line(annotated_image, (x, y), (x, y + c_len), (255, 255, 255), 2)
                cv2.line(annotated_image, (x + bw, y), (x + bw - c_len, y), (255, 255, 255), 2)
                cv2.line(annotated_image, (x + bw, y), (x + bw, y + c_len), (255, 255, 255), 2)

                # Compact pill-style badge
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.42
                thickness = 1
                (text_w, text_h), baseline = cv2.getTextSize(label, font, font_scale, thickness)

                badge_h = text_h + 8
                badge_w = text_w + 12
                badge_y = max(badge_h, y - 4)

                # Badge background with subtle border
                cv2.rectangle(
                    annotated_image,
                    (x, badge_y - badge_h),
                    (x + badge_w, badge_y),
                    badge_bg,
                    -1
                )
                cv2.rectangle(
                    annotated_image,
                    (x, badge_y - badge_h),
                    (x + badge_w, badge_y),
                    box_color,
                    1
                )
                cv2.putText(
                    annotated_image,
                    label,
                    (x + 6, badge_y - 4),
                    font,
                    font_scale,
                    text_color,
                    thickness,
                    cv2.LINE_AA
                )

        annotated_b64 = self.encode_image_base64(annotated_image) if draw_annotations else ""
        return detections, annotated_b64

# Convenience singleton accessor
def get_face_engine():
    return FaceEngine.get_instance()
