import io
import os
import cv2
import base64
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, Response, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

import database as db
from face_engine import get_face_engine
import email_service
import auth_service

ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
PHOTOS_DIR = ROOT / "student_photos"
STATIC_DIR.mkdir(exist_ok=True)
PHOTOS_DIR.mkdir(exist_ok=True)

# Initialize and seed database
db.init_db()
db.seed_existing_data()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-warm the FaceEngine at startup so the first recognition is instant."""
    import asyncio
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, get_face_engine)
    print("[Server] FaceEngine pre-warmed and ready.")
    yield

app = FastAPI(title="AI Classroom Attendance System", version="2.3.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static and photo directories
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/student_photos", StaticFiles(directory=str(PHOTOS_DIR)), name="student_photos")

# ----------------- Root & Navigation ----------------- #

@app.get("/api/network-info")
async def get_network_info():
    import socket
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        primary_ip = s.getsockname()[0]
        s.close()
        ips.append(primary_ip)
    except Exception:
        pass
    
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except Exception:
        pass

    primary = ips[0] if ips else "localhost"
    return {
        "primary_ip": primary,
        "port": 8000,
        "mobile_url": f"http://{primary}:8000"
    }

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return HTMLResponse("<h1>AI Attendance System: Frontend loading...</h1>")
    return FileResponse(str(index_file))

@app.get("/onboarding", response_class=HTMLResponse)
@app.get("/register", response_class=HTMLResponse)
@app.get("/student-onboarding", response_class=HTMLResponse)
async def serve_onboarding():
    onboarding_file = STATIC_DIR / "onboarding.html"
    if not onboarding_file.exists():
        return HTMLResponse("<h1>Student Onboarding Portal: Loading...</h1>")
    return FileResponse(str(onboarding_file))

# ----------------- Student Self-Service Onboarding API ----------------- #

class SendOtpRequest(BaseModel):
    email: str
    name: Optional[str] = ""

@app.post("/api/onboarding/send-otp")
async def send_otp_endpoint(payload: SendOtpRequest):
    email = payload.email.strip().lower()
    if "@" not in email or "." not in email:
        raise HTTPException(status_code=400, detail="Please provide a valid institute email address.")

    if not email_service.is_allowed_domain(email):
        allowed = ", ".join(email_service.ALLOWED_DOMAINS)
        raise HTTPException(status_code=400, detail=f"Registration is restricted to official institute email domains ({allowed}).")

    # Rate limiting & spam protection
    allowed, rate_msg = auth_service.check_otp_rate_limit(email)
    if not allowed:
        raise HTTPException(status_code=429, detail=rate_msg)

    # Check if student with this email is already registered
    existing = db.get_student_by_email(email)
    if existing:
        raise HTTPException(status_code=400, detail=f"A student with email '{email}' is already enrolled ({existing['roll_no']}: {existing['name']}).")

    otp = email_service.generate_otp()
    otp_hash = email_service.hash_otp(otp, email)
    expires_at = datetime.now() + email_service.timedelta(minutes=10)

    db.save_email_otp(email, otp_hash, expires_at)
    res = email_service.send_verification_email(email, otp, student_name=payload.name)
    return res

class VerifyOtpRequest(BaseModel):
    email: str
    otp: str

@app.post("/api/onboarding/verify-otp")
async def verify_otp_endpoint(payload: VerifyOtpRequest):
    email = payload.email.strip().lower()
    otp = payload.otp.strip()
    if not email or not otp:
        raise HTTPException(status_code=400, detail="Email and OTP code are required.")

    def check_fn(stored_hash: str):
        computed_hash = email_service.hash_otp(otp, email)
        return computed_hash == stored_hash

    ok = db.verify_email_otp(email, check_fn)
    if not ok:
        attempts_left = auth_service.record_failed_otp_attempt(email)
        if attempts_left == 0:
            raise HTTPException(status_code=429, detail="Too many failed OTP attempts. This account is locked for 15 minutes for security.")
        raise HTTPException(status_code=400, detail=f"Invalid or expired OTP code. {attempts_left} attempt(s) remaining before security lockout.")

    auth_service.reset_failed_otp_attempts(email)

    # Issue cryptographically signed HMAC-SHA256 onboarding token (25-minute lifespan)
    token = auth_service.generate_onboarding_token(email, expiry_minutes=25)

    return {
        "success": True,
        "message": "Institute email verified successfully! Proceed to upload your 4 photos.",
        "token": token,
        "email": email,
        "expires_in": 1500
    }

@app.post("/api/onboarding/submit")
async def submit_student_onboarding(
    request: Request,
    email: str = Form(...),
    roll_no: str = Form(...),
    name: str = Form(...),
    branch: str = Form(...),
    onboarding_token: Optional[str] = Form(None),
    photos: Optional[List[UploadFile]] = File(None),
    photos_b64: Optional[str] = Form(None),
    auto_generate_embeddings: bool = Form(True)
):
    import json
    email = email.strip().lower()
    roll_no = roll_no.strip().upper()
    name = name.strip()
    branch = branch.strip()

    # 1. Cryptographic Authentication & Token Verification
    # Accepts token from Authorization header or form parameter
    auth_header = request.headers.get("Authorization", "")
    token = onboarding_token
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()

    is_valid, token_payload, auth_err = auth_service.verify_onboarding_token(token, expected_email=email)
    if not is_valid:
        raise HTTPException(
            status_code=401,
            detail=f"Authentication failed: {auth_err} Please re-verify your institute email."
        )

    # 2. Check roll no collision
    if db.get_student_by_roll(roll_no):
        raise HTTPException(status_code=400, detail=f"Roll Number '{roll_no}' is already registered in the system.")

    # 3. Decode photos (files or base64 snapshots from phone camera)
    engine = get_face_engine()
    raw_images = []

    if photos:
        for f in photos:
            if f.filename:
                content = await f.read()
                img = engine.decode_image_bytes(content)
                if img is not None and img.size > 0:
                    raw_images.append((img, f.filename))

    if photos_b64:
        try:
            parsed = json.loads(photos_b64)
            if not isinstance(parsed, list):
                parsed = [parsed]
            for idx, b64_item in enumerate(parsed):
                s = str(b64_item)
                if "," in s:
                    s = s.split(",", 1)[1]
                b_bytes = base64.b64decode(s)
                img = engine.decode_image_bytes(b_bytes)
                if img is not None and img.size > 0:
                    raw_images.append((img, f"photo_angle_{idx+1}.jpg"))
        except Exception as e:
            print("[Onboarding] Error decoding base64 photos:", e)

    if len(raw_images) < 4:
        raise HTTPException(status_code=400, detail=f"Please provide all 4 requested photos (Forward, Left Tilt, Right Tilt, Slight Smile). Received only {len(raw_images)}.")

    # 4. Save photos to student directory on disk
    clean_name = "".join(c for c in name if c.isalnum() or c in (" ", "_", "-")).strip()
    student_dir = PHOTOS_DIR / clean_name
    student_dir.mkdir(parents=True, exist_ok=True)

    saved_photo_paths = []
    valid_embeddings = []
    first_photo_rel = None

    for idx, (img_bgr, orig_name) in enumerate(raw_images, start=1):
        filename = f"{roll_no}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{idx}.jpg"
        dest_path = student_dir / filename
        cv2.imwrite(str(dest_path), img_bgr)
        rel_path = str(dest_path.relative_to(ROOT))
        saved_photo_paths.append(rel_path)

        if first_photo_rel is None:
            first_photo_rel = rel_path

        # If auto_generate_embeddings is requested, calculate embedding now;
        # otherwise, batch script `generate_embeddings.py` can be run anytime later!
        if auto_generate_embeddings:
            try:
                emb, err = engine.extract_single_face_embedding(img_bgr)
                if not err and emb is not None:
                    valid_embeddings.append((emb, rel_path))
            except Exception as ex:
                print(f"[Onboarding] Extraction note for photo {idx}:", ex)

    # 5. Insert student into database
    student_id = db.add_student(
        roll_no=roll_no,
        name=name,
        branch=branch,
        photo_path=first_photo_rel,
        embeddings=valid_embeddings if auto_generate_embeddings else None,
        email=email
    )

    # 6. Auto-enroll in all courses
    courses = db.get_all_courses()
    for c in courses:
        db.enroll_student_in_course(c["id"], student_id)

    # 7. Single-use token invalidation (anti-replay)
    if token_payload and "jti" in token_payload:
        auth_service.consume_onboarding_token(token_payload["jti"])

    return {
        "success": True,
        "student_id": student_id,
        "roll_no": roll_no,
        "name": name,
        "branch": branch,
        "email": email,
        "photos_saved": len(saved_photo_paths),
        "embeddings_created": len(valid_embeddings),
        "message": f"Welcome, {name}! Your data and 4 photos were collected successfully. You are now enrolled in the AI Attendance System."
    }

# ----------------- Students API ----------------- #

@app.get("/api/students")
async def list_students():
    return db.get_all_students()

@app.post("/api/students")
async def register_student(
    roll_no: str = Form(...),
    name: str = Form(...),
    branch: str = Form(...),
    photos: Optional[List[UploadFile]] = File(None),
    photo: Optional[UploadFile] = File(None),
    photos_b64: Optional[str] = Form(None),
    photo_b64: Optional[str] = Form(None)
):
    import json
    existing = db.get_student_by_roll(roll_no)
    if existing:
        raise HTTPException(status_code=400, detail=f"Student with Roll No '{roll_no}' already exists.")

    engine = get_face_engine()
    raw_images = []

    # 1. Gather all file uploads
    all_files = []
    if photos:
        all_files.extend(photos)
    if photo and photo.filename:
        all_files.append(photo)

    for f in all_files:
        if f.filename:
            content = await f.read()
            img = engine.decode_image_bytes(content)
            if img is not None and img.size > 0:
                raw_images.append((img, f.filename))

    # 2. Gather base64 images
    all_b64 = []
    if photos_b64:
        try:
            parsed = json.loads(photos_b64)
            if isinstance(parsed, list):
                all_b64.extend(parsed)
            else:
                all_b64.append(str(parsed))
        except Exception:
            all_b64.append(photos_b64)
    if photo_b64:
        all_b64.append(photo_b64)

    for idx, b64_item in enumerate(all_b64):
        s = b64_item
        if "," in s:
            s = s.split(",", 1)[1]
        try:
            b_bytes = base64.b64decode(s)
            img = engine.decode_image_bytes(b_bytes)
            if img is not None and img.size > 0:
                raw_images.append((img, f"snapshot_{idx+1}.jpg"))
        except Exception:
            pass

    if not raw_images:
        raise HTTPException(status_code=400, detail="Please provide at least one valid portrait photo.")

    clean_name = "".join(c for c in name if c.isalnum() or c in (" ", "_", "-")).strip()
    student_dir = PHOTOS_DIR / clean_name
    student_dir.mkdir(parents=True, exist_ok=True)

    valid_embeddings = []
    errors = []
    first_photo_path = None

    for idx, (img_bgr, orig_name) in enumerate(raw_images, start=1):
        embedding, err = engine.extract_single_face_embedding(img_bgr)
        if err:
            errors.append(f"{orig_name}: {err}")
            continue

        filename = f"{roll_no.strip().upper()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{idx}.jpg"
        dest_path = student_dir / filename
        cv2.imwrite(str(dest_path), img_bgr)
        rel_path = str(dest_path.relative_to(ROOT))

        if first_photo_path is None:
            first_photo_path = rel_path

        valid_embeddings.append((embedding, rel_path))

    if not valid_embeddings:
        err_msg = " | ".join(errors) if errors else "No face detected in the provided photos."
        raise HTTPException(status_code=400, detail=f"No valid faces extracted: {err_msg}")

    student_id = db.add_student(
        roll_no=roll_no,
        name=name,
        branch=branch,
        photo_path=first_photo_path,
        embeddings=valid_embeddings
    )

    # Automatically enroll new student in all existing courses
    courses = db.get_all_courses()
    for c in courses:
        db.enroll_student_in_course(c["id"], student_id)

    msg = f"Successfully registered {name} ({roll_no}) with {len(valid_embeddings)} facial embedding(s)!"
    if errors:
        msg += f" Note: {len(errors)} photo(s) skipped due to unclear faces."

    return {
        "success": True,
        "message": msg,
        "student_id": student_id,
        "photo_path": first_photo_path,
        "total_embeddings": len(valid_embeddings)
    }

@app.post("/api/students/{student_id}/add-photos")
async def add_photos_to_existing_student(
    student_id: int,
    photos: Optional[List[UploadFile]] = File(None),
    photo: Optional[UploadFile] = File(None),
    photos_b64: Optional[str] = Form(None),
    photo_b64: Optional[str] = Form(None)
):
    import json
    student = db.get_student_by_id(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    engine = get_face_engine()
    raw_images = []

    all_files = []
    if photos:
        all_files.extend(photos)
    if photo and photo.filename:
        all_files.append(photo)

    for f in all_files:
        if f.filename:
            content = await f.read()
            img = engine.decode_image_bytes(content)
            if img is not None and img.size > 0:
                raw_images.append((img, f.filename))

    all_b64 = []
    if photos_b64:
        try:
            parsed = json.loads(photos_b64)
            if isinstance(parsed, list):
                all_b64.extend(parsed)
            else:
                all_b64.append(str(parsed))
        except Exception:
            all_b64.append(photos_b64)
    if photo_b64:
        all_b64.append(photo_b64)

    for idx, b64_item in enumerate(all_b64):
        s = b64_item
        if "," in s:
            s = s.split(",", 1)[1]
        try:
            b_bytes = base64.b64decode(s)
            img = engine.decode_image_bytes(b_bytes)
            if img is not None and img.size > 0:
                raw_images.append((img, f"snapshot_{idx+1}.jpg"))
        except Exception:
            pass

    if not raw_images:
        raise HTTPException(status_code=400, detail="Please provide at least one photo.")

    clean_name = "".join(c for c in student["name"] if c.isalnum() or c in (" ", "_", "-")).strip()
    student_dir = PHOTOS_DIR / clean_name
    student_dir.mkdir(parents=True, exist_ok=True)

    added_count = 0
    errors = []

    for idx, (img_bgr, orig_name) in enumerate(raw_images, start=1):
        embedding, err = engine.extract_single_face_embedding(img_bgr)
        if err:
            errors.append(f"{orig_name}: {err}")
            continue

        filename = f"{student['roll_no'].strip().upper()}_extra_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{idx}.jpg"
        dest_path = student_dir / filename
        cv2.imwrite(str(dest_path), img_bgr)
        rel_path = str(dest_path.relative_to(ROOT))

        db.add_embedding_to_student(student_id, embedding, rel_path)
        added_count += 1

    if added_count == 0:
        err_msg = " | ".join(errors) if errors else "No face detected in the provided photos."
        raise HTTPException(status_code=400, detail=f"Failed to add photos: {err_msg}")

    return {
        "success": True,
        "message": f"Added {added_count} new facial photo(s) to {student['name']}!",
        "added_count": added_count
    }

class UpdateStudentModel(BaseModel):
    name: Optional[str] = None
    roll_no: Optional[str] = None
    branch: Optional[str] = None

@app.patch("/api/students/{student_id}")
@app.put("/api/students/{student_id}")
async def update_student_info(student_id: int, payload: UpdateStudentModel):
    student = db.get_student_by_id(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")
    db.update_student(student_id, name=payload.name, roll_no=payload.roll_no, branch=payload.branch)
    return {"success": True, "student": db.get_student_by_id(student_id)}

# ----------------- Courses API ----------------- #

class CreateCourseModel(BaseModel):
    code: str
    name: str
    branch: str

@app.get("/api/courses")
async def list_courses():
    return db.get_all_courses()

@app.post("/api/courses")
async def create_course(payload: CreateCourseModel):
    try:
        cid = db.create_course(payload.code, payload.name, payload.branch)
        # Automatically enroll existing students
        students = db.get_all_students()
        for s in students:
            db.enroll_student_in_course(cid, s["id"])
        return {"success": True, "course_id": cid}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create course: {str(e)}")

@app.get("/api/courses/{course_id}/students")
async def get_course_students(course_id: int):
    return db.get_course_enrolled_students(course_id)

@app.get("/api/courses/{course_id}/unenrolled-students")
async def get_unenrolled_students(course_id: int):
    return db.get_unenrolled_students(course_id)

class EnrollPayload(BaseModel):
    student_id: int

@app.post("/api/courses/{course_id}/enroll")
async def enroll_student(course_id: int, payload: Optional[EnrollPayload] = None, student_id: Optional[int] = Form(None)):
    sid = payload.student_id if payload else student_id
    if not sid:
        raise HTTPException(status_code=400, detail="student_id is required")
    db.enroll_student_in_course(course_id, sid)
    return {"success": True, "message": "Student enrolled successfully"}

@app.post("/api/courses/{course_id}/unenroll")
async def unenroll_student(course_id: int, payload: EnrollPayload):
    db.unenroll_student_from_course(course_id, payload.student_id)
    return {"success": True, "message": "Student unenrolled successfully"}

@app.get("/api/courses/{course_id}/report")
async def get_course_report(course_id: int):
    data = db.get_course_attendance_report(course_id)
    if not data:
        raise HTTPException(status_code=404, detail="Course not found")
    return data

@app.delete("/api/courses/{course_id}")
async def delete_course_endpoint(course_id: int):
    course = db.get_course_by_id(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    db.delete_course(course_id)
    return {
        "success": True,
        "message": f"Course '{course['code']}' ({course['name']}) and its sessions were deleted successfully."
    }

# ----------------- Sessions API ----------------- #

class CreateSessionModel(BaseModel):
    course_id: int
    title: str
    session_date: Optional[str] = None
    session_time: Optional[str] = None

@app.get("/api/sessions")
async def list_sessions(course_id: Optional[int] = None):
    return db.get_all_sessions(course_id)

@app.post("/api/sessions")
async def create_session(payload: CreateSessionModel):
    try:
        sid = db.create_session(payload.course_id, payload.title, payload.session_date, payload.session_time)
        return {"success": True, "session_id": sid}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create session: {str(e)}")

@app.get("/api/sessions/{session_id}")
async def get_session_info(session_id: int):
    session = db.get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session

@app.get("/api/sessions/{session_id}/attendance")
async def get_session_attendance(session_id: int):
    session = db.get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    records = db.get_session_attendance_list(session_id)
    return {
        "session": session,
        "records": records
    }

class AttendanceUpdateModel(BaseModel):
    student_id: int
    status: str

@app.post("/api/sessions/{session_id}/attendance/toggle")
async def toggle_student_attendance(session_id: int, payload: AttendanceUpdateModel):
    db.mark_student_attendance(
        session_id=session_id,
        student_id=payload.student_id,
        status=payload.status,
        confidence=1.0,
        method="Manual Override"
    )
    return {"success": True}

# ----------------- AI Face Recognition Attendance ----------------- #

@app.post("/api/attendance/recognize-group")
async def recognize_group_attendance(
    session_id: int = Form(...),
    image: Optional[UploadFile] = File(None),
    images: Optional[List[UploadFile]] = File(None),
    threshold: float = Form(0.38)
):
    session = db.get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    raw_files = []
    if images:
        raw_files.extend(images)
    if image and image.filename:
        raw_files.append(image)
    if not raw_files:
        raise HTTPException(status_code=400, detail="Please upload or snap at least one classroom image.")

    engine = get_face_engine()
    known_emb, known_ids, id_meta = db.get_registered_embeddings_for_session(session_id)

    total_faces = 0
    annotated_images_b64 = []
    all_detections = []
    matched_students_map = {}

    for idx, f in enumerate(raw_files, start=1):
        image_bytes = await f.read()
        image_bgr = engine.decode_image_bytes(image_bytes)
        if image_bgr is None or image_bgr.size == 0:
            continue

        dets, annotated_b64 = engine.recognize_faces_in_image(
            image_bgr,
            known_embeddings=known_emb,
            known_student_ids=known_ids,
            id_meta_map=id_meta,
            threshold=threshold,
            draw_annotations=True
        )

        total_faces += len(dets)
        all_detections.extend(dets)
        if annotated_b64:
            annotated_images_b64.append(annotated_b64)

        for det in dets:
            if det["is_matched"] and det["student_id"]:
                sid = det["student_id"]
                score = det["score"]
                if sid not in matched_students_map or score > matched_students_map[sid]["score"]:
                    matched_students_map[sid] = {
                        "name": det["name"],
                        "score": score
                    }

    # Mark all unique identified students as Present in one single atomic transaction
    updates = [
        {
            "student_id": sid,
            "status": "Present",
            "confidence": info["score"],
            "method": "Group Photo AI"
        }
        for sid, info in matched_students_map.items()
    ]
    db.mark_students_attendance_batch(session_id, updates)

    updated_records = db.get_session_attendance_list(session_id)

    return {
        "success": True,
        "total_images_processed": len(raw_files),
        "total_faces_detected": total_faces,
        "recognized_students_count": len(matched_students_map),
        "recognized_names": sorted([info["name"] for info in matched_students_map.values()]),
        "annotated_image": annotated_images_b64[0] if annotated_images_b64 else "",
        "annotated_images": annotated_images_b64,
        "detections": all_detections,
        "updated_attendance": updated_records
    }

class LiveFrameModel(BaseModel):
    session_id: int
    frame_b64: str
    threshold: Optional[float] = 0.38

@app.post("/api/attendance/recognize-frame")
async def recognize_live_webcam_frame(payload: LiveFrameModel):
    session = db.get_session_by_id(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    b64_str = payload.frame_b64
    if "," in b64_str:
        b64_str = b64_str.split(",", 1)[1]

    frame_bytes = base64.b64decode(b64_str)
    frame_bgr = get_face_engine().decode_image_bytes(frame_bytes)
    if frame_bgr is None:
        raise HTTPException(status_code=400, detail="Invalid frame data.")

    known_emb, known_ids, id_meta = db.get_registered_embeddings_for_session(payload.session_id)
    engine = get_face_engine()

    detections, annotated_b64 = engine.recognize_faces_in_image(
        frame_bgr,
        known_embeddings=known_emb,
        known_student_ids=known_ids,
        id_meta_map=id_meta,
        threshold=payload.threshold or 0.38,
        draw_annotations=True
    )

    marked_students = []
    for det in detections:
        if det["is_matched"] and det["student_id"]:
            db.mark_student_attendance(
                session_id=payload.session_id,
                student_id=det["student_id"],
                status="Present",
                confidence=det["score"],
                method="Live Webcam AI"
            )
            marked_students.append(det["name"])

    return {
        "success": True,
        "detections": detections,
        "annotated_frame": annotated_b64,
        "marked_students": marked_students
    }

# ----------------- Student Portal API ----------------- #

@app.get("/api/student/{roll_no}/stats")
async def get_student_portal(roll_no: str):
    data = db.get_student_portal_stats(roll_no)
    if not data:
        raise HTTPException(status_code=404, detail=f"No student found with Roll No: '{roll_no}'.")
    return data

# ----------------- Export API (Excel & CSV) ----------------- #

@app.get("/api/export/excel")
async def export_excel(session_id: int = Query(...)):
    session = db.get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    records = db.get_session_attendance_list(session_id)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Attendance Sheet"

    # Styling constants (Sleek Black and White / Monochrome design)
    font_title = Font(name="Calibri", size=16, bold=True, color="000000")
    font_meta = Font(name="Calibri", size=11, bold=True, color="333333")
    font_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    font_data = Font(name="Calibri", size=10, color="000000")

    fill_header = PatternFill(start_color="1A1A1A", end_color="1A1A1A", fill_type="solid")
    fill_present = PatternFill(start_color="F0F0F0", end_color="F0F0F0", fill_type="solid")
    fill_absent = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")

    thin_border = Border(
        left=Side(style='thin', color='CCCCCC'),
        right=Side(style='thin', color='CCCCCC'),
        top=Side(style='thin', color='CCCCCC'),
        bottom=Side(style='thin', color='CCCCCC')
    )

    # Title Block
    ws.merge_cells("A1:G1")
    ws["A1"] = "CLASSROOM ATTENDANCE REPORT"
    ws["A1"].font = font_title
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 30

    # Metadata
    total_students = len(records)
    present_students = sum(1 for r in records if r["status"] == "Present")
    absent_students = total_students - present_students
    pct = round((present_students / total_students * 100), 1) if total_students > 0 else 0

    meta_rows = [
        ("Course:", f"{session['course_code']} - {session['course_name']}", "Date:", session["session_date"]),
        ("Session Title:", session["title"], "Branch:", session["course_branch"]),
        ("Total Enrolled:", total_students, "Attendance Rate:", f"{pct}% ({present_students} Present, {absent_students} Absent)")
    ]

    for r_idx, row in enumerate(meta_rows, start=2):
        ws.cell(row=r_idx, column=1, value=row[0]).font = font_meta
        ws.cell(row=r_idx, column=2, value=row[1]).font = font_data
        ws.cell(row=r_idx, column=4, value=row[2]).font = font_meta
        ws.cell(row=r_idx, column=5, value=row[3]).font = font_data
        ws.row_dimensions[r_idx].height = 20

    # Table Headers
    headers = ["S.No", "Roll Number", "Student Name", "Branch", "Status", "Confidence", "Verification Method"]
    start_row = 6
    ws.row_dimensions[start_row].height = 24

    for c_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=start_row, column=c_idx, value=header)
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border

    # Data Rows
    for idx, r in enumerate(records, start=1):
        row_num = start_row + idx
        ws.row_dimensions[row_num].height = 20
        status_val = r["status"]
        conf_val = f"{int(r['confidence'] * 100)}%" if r["confidence"] > 0 else "-"

        vals = [idx, r["roll_no"], r["name"], r["branch"], status_val, conf_val, r["marked_method"]]
        for col_idx, val in enumerate(vals, start=1):
            c = ws.cell(row=row_num, column=col_idx, value=val)
            c.font = font_data
            c.border = thin_border
            c.alignment = Alignment(horizontal="center" if col_idx in [1, 2, 5, 6] else "left", vertical="center")
            if status_val == "Present":
                c.fill = fill_present

    # Column widths
    col_widths = [8, 16, 24, 20, 14, 16, 22]
    for i, w in enumerate(col_widths, start=1):
        col_letter = openpyxl.utils.get_column_letter(i)
        ws.column_dimensions[col_letter].width = w

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"Attendance_{session['course_code']}_{session['session_date']}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@app.get("/api/export/csv")
async def export_csv(session_id: int = Query(...)):
    session = db.get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    records = db.get_session_attendance_list(session_id)
    df_rows = []
    for idx, r in enumerate(records, 1):
        df_rows.append({
            "S.No": idx,
            "Roll No": r["roll_no"],
            "Name": r["name"],
            "Branch": r["branch"],
            "Course Code": session["course_code"],
            "Course Name": session["course_name"],
            "Session Title": session["title"],
            "Date": session["session_date"],
            "Status": r["status"],
            "Confidence": f"{int(r['confidence'] * 100)}%" if r["confidence"] > 0 else "N/A",
            "Marked Method": r["marked_method"],
            "Timestamp": r["marked_at"] or ""
        })

    df = pd.DataFrame(df_rows)
    stream = io.StringIO()
    df.to_csv(stream, index=False)
    stream.seek(0)

    filename = f"Attendance_{session['course_code']}_{session['session_date']}.csv"
    return StreamingResponse(
        io.BytesIO(stream.getvalue().encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

# ----------------- Course-Wise Cumulative Attendance Export ----------------- #

@app.get("/api/export/course/excel")
async def export_course_excel(course_id: int = Query(...)):
    report = db.get_course_attendance_report(course_id)
    if not report:
        raise HTTPException(status_code=404, detail="Course not found.")

    course = report["course"]
    sessions = report["sessions"]
    students = report["students"]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"{course['code']} Summary"

    font_title = Font(name="Calibri", size=15, bold=True, color="000000")
    font_meta = Font(name="Calibri", size=10, bold=True, color="333333")
    font_header = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    font_data = Font(name="Calibri", size=9, color="000000")
    font_bold = Font(name="Calibri", size=9, bold=True, color="000000")
    font_present = Font(name="Calibri", size=9, bold=True, color="166534")
    font_absent = Font(name="Calibri", size=9, bold=True, color="991B1B")

    fill_header = PatternFill(start_color="18181B", end_color="18181B", fill_type="solid")
    fill_sub_header = PatternFill(start_color="27272A", end_color="27272A", fill_type="solid")
    fill_eligible = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")   # soft green
    fill_shortage = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")   # soft red
    fill_present = PatternFill(start_color="F0FDF4", end_color="F0FDF4", fill_type="solid")
    fill_absent = PatternFill(start_color="FEF2F2", end_color="FEF2F2", fill_type="solid")

    thin_border = Border(
        left=Side(style='thin', color='CCCCCC'),
        right=Side(style='thin', color='CCCCCC'),
        top=Side(style='thin', color='CCCCCC'),
        bottom=Side(style='thin', color='CCCCCC')
    )

    # Title & Metadata
    num_cols = 8 + len(sessions)
    last_col_letter = openpyxl.utils.get_column_letter(max(8, num_cols))
    ws.merge_cells(f"A1:{last_col_letter}1")
    ws["A1"] = f"COURSE ATTENDANCE & PERFORMANCE SUMMARY: {course['code']} - {course['name']}"
    ws["A1"].font = font_title
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 28

    meta_rows = [
        ("Course Code:", course["code"], "Department:", course["branch"]),
        ("Total Classes Held:", len(sessions), "Enrolled Students:", len(students)),
        ("Generated On:", datetime.now().strftime("%Y-%m-%d %H:%M"), "Minimum Requirement:", "75.0% Attendance")
    ]
    for r_idx, row in enumerate(meta_rows, start=2):
        ws.cell(row=r_idx, column=1, value=row[0]).font = font_meta
        ws.cell(row=r_idx, column=2, value=row[1]).font = font_data
        ws.cell(row=r_idx, column=4, value=row[2]).font = font_meta
        ws.cell(row=r_idx, column=5, value=row[3]).font = font_data
        ws.row_dimensions[r_idx].height = 18

    # Table Header
    start_row = 6
    ws.row_dimensions[start_row].height = 26
    fixed_headers = ["S.No", "Roll Number", "Student Name", "Branch", "Total Classes", "Classes Attended", "Attendance %", "Status"]

    for col_idx, h in enumerate(fixed_headers, start=1):
        cell = ws.cell(row=start_row, column=col_idx, value=h)
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border

    # Dynamic session headers
    for idx, sess in enumerate(sessions, start=len(fixed_headers) + 1):
        cell = ws.cell(row=start_row, column=idx, value=f"{sess['session_date']}\n{sess['title'][:14]}")
        cell.font = font_header
        cell.fill = fill_sub_header
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border

    # Data Rows
    for idx, st in enumerate(students, start=1):
        row_num = start_row + idx
        ws.row_dimensions[row_num].height = 20

        is_eligible = st["is_eligible"]
        status_text = "ELIGIBLE" if is_eligible else "SHORTAGE"
        row_fill = fill_eligible if is_eligible else fill_shortage

        vals = [
            idx,
            st["roll_no"],
            st["name"],
            st["branch"],
            st["total_sessions"],
            st["attended_sessions"],
            f"{st['percentage']}%",
            status_text
        ]

        for col_idx, val in enumerate(vals, start=1):
            cell = ws.cell(row=row_num, column=col_idx, value=val)
            cell.font = font_bold if col_idx in [2, 7, 8] else font_data
            cell.border = thin_border
            cell.alignment = Alignment(horizontal="center" if col_idx in [1, 2, 5, 6, 7, 8] else "left", vertical="center")
            if col_idx in [7, 8]:
                cell.fill = row_fill

        # Session attendance cells (P or A)
        for s_idx, sess in enumerate(sessions, start=len(fixed_headers) + 1):
            sess_rec = st["sessions"].get(sess["id"], {})
            sess_status = sess_rec.get("status", "Absent")
            c = ws.cell(row=row_num, column=s_idx, value="P" if sess_status == "Present" else "A")
            c.font = font_present if sess_status == "Present" else font_absent
            c.fill = fill_present if sess_status == "Present" else fill_absent
            c.border = thin_border
            c.alignment = Alignment(horizontal="center", vertical="center")

    # Column Widths
    col_widths = {1: 7, 2: 15, 3: 22, 4: 18, 5: 14, 6: 16, 7: 15, 8: 14}
    for col_idx, w in col_widths.items():
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = w
    for s_idx in range(len(fixed_headers) + 1, len(fixed_headers) + 1 + len(sessions)):
        ws.column_dimensions[openpyxl.utils.get_column_letter(s_idx)].width = 13

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"Course_Attendance_{course['code']}_{datetime.now().strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@app.get("/api/export/course/csv")
async def export_course_csv(course_id: int = Query(...)):
    report = db.get_course_attendance_report(course_id)
    if not report:
        raise HTTPException(status_code=404, detail="Course not found.")

    course = report["course"]
    sessions = report["sessions"]
    students = report["students"]

    rows = []
    for idx, st in enumerate(students, 1):
        row = {
            "S.No": idx,
            "Roll No": st["roll_no"],
            "Name": st["name"],
            "Branch": st["branch"],
            "Course Code": course["code"],
            "Course Name": course["name"],
            "Total Sessions": st["total_sessions"],
            "Attended Sessions": st["attended_sessions"],
            "Attendance Percentage": f"{st['percentage']}%",
            "Eligibility (75%)": "ELIGIBLE" if st["is_eligible"] else "SHORTAGE"
        }
        for sess in sessions:
            s_rec = st["sessions"].get(sess["id"], {})
            row[f"Session_{sess['session_date']}_{sess['title']}"] = s_rec.get("status", "Absent")
        rows.append(row)

    df = pd.DataFrame(rows)
    stream = io.StringIO()
    df.to_csv(stream, index=False)
    stream.seek(0)

    filename = f"Course_Attendance_{course['code']}_{datetime.now().strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        io.BytesIO(stream.getvalue().encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@app.get("/api/download/presentation")
async def download_presentation():
    candidates = [
        "AI_Classroom_Attendance_Presentation_Updated.pptx",
        "AI_Classroom_Attendance_Presentation_White.pptx",
        "AI_Classroom_Attendance_Presentation.pptx"
    ]
    valid_paths = [os.path.join(os.path.dirname(__file__), c) for c in candidates if os.path.exists(os.path.join(os.path.dirname(__file__), c))]
    if valid_paths:
        ppt_path = max(valid_paths, key=os.path.getmtime)
    else:
        ppt_path = os.path.join(os.path.dirname(__file__), "AI_Classroom_Attendance_Presentation_Updated.pptx")
        import generate_presentation
        generate_presentation.create_presentation(ppt_path)
    return FileResponse(
        ppt_path,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename="AURA_AI_Classroom_Attendance_Presentation.pptx"
    )

@app.get("/api/download/math-ml-guide")
async def download_math_ml_guide():
    pdf_path = os.path.join(os.path.dirname(__file__), "AI_Classroom_Attendance_Math_and_ML_Guide.pdf")
    if not os.path.exists(pdf_path):
        import generate_teaching_pdf
        generate_teaching_pdf.create_teaching_pdf(pdf_path)
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename="AURA_AI_Classroom_Attendance_Math_and_ML_Guide.pdf"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
