"""
SAHI (Slicing Aided Hyper Inference) Face Engine Module
Implements research-grade sliced detection and adaptive facial enhancement
for high-density, distant classroom environments.
"""

import cv2
import numpy as np
from pathlib import Path
from face_engine import get_face_engine
from insightface.utils.face_align import norm_crop
import database as db

class SAHIFaceEngine:
    def __init__(self, slice_size=(640, 640), overlap_ratio=0.25):
        self.base_engine = get_face_engine()
        self.slice_w, self.slice_h = slice_size
        self.overlap_ratio = overlap_ratio

    def generate_slices(self, img_w: int, img_h: int):
        """Generates bounding coordinates for overlapping slices."""
        step_x = int(self.slice_w * (1.0 - self.overlap_ratio))
        step_y = int(self.slice_h * (1.0 - self.overlap_ratio))

        slices = []
        y = 0
        while y < img_h:
            x = 0
            while x < img_w:
                x2 = min(x + self.slice_w, img_w)
                y2 = min(y + self.slice_h, img_h)
                x1 = max(0, x2 - self.slice_w)
                y1 = max(0, y2 - self.slice_h)
                slices.append((x1, y1, x2 - x1, y2 - y1))
                if x2 >= img_w:
                    break
                x += step_x
            if y2 >= img_h:
                break
            y += step_y

        return list(dict.fromkeys(slices))

    def detect_sahi_faces(self, image_bgr: np.ndarray, conf_threshold: float = 0.40):
        """
        Runs Slicing Aided Hyper Inference (SAHI) on high-resolution image.
        Detects faces in overlapping native-scale slices and merges via NMS.
        """
        img_h, img_w = image_bgr.shape[:2]
        all_candidates = []

        # 1. Full-frame pass (catches large foreground subjects)
        self.base_engine.detector.setInputSize((img_w, img_h))
        _, full_faces = self.base_engine.detector.detect(image_bgr)
        if full_faces is not None:
            for f in full_faces:
                if f[-1] >= conf_threshold:
                    all_candidates.append(f)

        # 2. Sliced inference pass (preserves native pixel density for distant faces)
        slice_coords = self.generate_slices(img_w, img_h)
        for sx, sy, sw, sh in slice_coords:
            tile = image_bgr[sy:sy + sh, sx:sx + sw]
            self.base_engine.detector.setInputSize((sw, sh))
            _, tile_faces = self.base_engine.detector.detect(tile)
            if tile_faces is not None:
                for f in tile_faces:
                    if f[-1] >= conf_threshold:
                        # Translate bounding box and 5 landmarks to global image coordinates
                        f_global = f.copy()
                        f_global[0] += sx
                        f_global[1] += sy
                        # Landmarks (5 points: x at indices 4,6,8,10,12; y at 5,7,9,11,13)
                        for k in range(5):
                            f_global[4 + k * 2] += sx
                            f_global[5 + k * 2] += sy
                        all_candidates.append(f_global)

        if not all_candidates:
            return []

        # 3. Non-Maximum Suppression (NMS) across slices and full frame
        all_candidates.sort(key=lambda x: float(x[-1]), reverse=True)
        suppressed = []

        for f in all_candidates:
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
                    if iou > 0.35 or iom > 0.50:
                        is_overlap = True
                        break

            if not is_overlap:
                suppressed.append(f)

        return suppressed

    @staticmethod
    def enhance_face_crop(crop_bgr: np.ndarray) -> np.ndarray:
        """
        Enhances low-resolution, distant, or backlit faces before ArcFace embedding.
        Uses CLAHE on the L-channel + subpixel unsharp masking.
        """
        if crop_bgr is None or crop_bgr.size == 0:
            return crop_bgr

        # 1. CLAHE in LAB space (recovers facial details in shadow/backlight)
        lab = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(4, 4))
        l_enhanced = clahe.apply(l)
        enhanced_lab = cv2.merge((l_enhanced, a, b))
        bgr_enhanced = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)

        # 2. Mild unsharp masking for sharp edge gradients on eyes & nose
        blurred = cv2.GaussianBlur(bgr_enhanced, (0, 0), sigmaX=1.5)
        sharp = cv2.addWeighted(bgr_enhanced, 1.25, blurred, -0.25, 0)
        return sharp

    def recognize_with_sahi(
        self,
        image_bgr: np.ndarray,
        known_embeddings: np.ndarray,
        known_student_ids: np.ndarray,
        id_meta_map: dict,
        threshold: float = 0.34
    ):
        """
        Full SAHI + Adaptive Enhancement Recognition pipeline.
        Returns detections list and stats.
        """
        faces = self.detect_sahi_faces(image_bgr, conf_threshold=0.40)
        img_h, img_w = image_bgr.shape[:2]

        student_groups = {}
        for idx, sid in enumerate(known_student_ids):
            sid = int(sid)
            if sid not in student_groups:
                student_groups[sid] = []
            student_groups[sid].append(known_embeddings[idx])
        for sid in student_groups:
            student_groups[sid] = np.array(student_groups[sid], dtype=np.float32)

        results = []
        for face in faces:
            fx, fy, fw, fh = map(int, face[:4])
            fx = max(0, min(img_w - 1, fx))
            fy = max(0, min(img_h - 1, fy))
            fw = max(1, min(img_w - fx, fw))
            fh = max(1, min(img_h - fy, fh))

            lms = face[4:14].reshape(5, 2).astype(np.float32)
            
            # Align face
            aligned = norm_crop(image_bgr, lms, image_size=112)

            # Standard ArcFace embedding
            emb1 = self.base_engine.recognizer.get_feat(aligned).flatten()
            norm1 = np.linalg.norm(emb1)
            if norm1 > 0:
                emb1 = emb1 / norm1

            # Enhanced ArcFace embedding for backlit/distant faces
            enhanced_aligned = self.enhance_face_crop(aligned)
            emb2 = self.base_engine.recognizer.get_feat(enhanced_aligned).flatten()
            norm2 = np.linalg.norm(emb2)
            if norm2 > 0:
                emb2 = emb2 / norm2

            best_sid = None
            best_score = -1.0

            for sid, s_embs in student_groups.items():
                # Test both standard and enhanced representations against student profile
                sims1 = s_embs @ emb1
                sims2 = s_embs @ emb2
                max_s = max(float(np.max(sims1)), float(np.max(sims2)))

                if max_s > best_score:
                    best_score = max_s
                    best_sid = sid

            is_matched = (best_score >= threshold and best_sid is not None)
            student_name = id_meta_map.get(best_sid, {}).get("name", "Unknown") if is_matched else "Unknown"
            student_roll = id_meta_map.get(best_sid, {}).get("roll_no", "") if is_matched else ""

            results.append({
                "bbox": [fx, fy, fw, fh],
                "student_id": best_sid if is_matched else None,
                "name": student_name,
                "roll_no": student_roll,
                "score": round(best_score, 3),
                "is_matched": is_matched
            })

        return results
