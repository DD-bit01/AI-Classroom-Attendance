"""
AURA.ai // Autonomous Facial Attendance & Biometric Intelligence Platform
Production-Ready Streamlit Cloud Deployment
"""

import streamlit as st
import cv2
import numpy as np
import pandas as pd
from PIL import Image
import os
import io
from pathlib import Path
from datetime import datetime

import database as db
from face_engine import get_face_engine

# --- Page Configuration ---
st.set_page_config(
    page_title="AURA // AI Classroom Attendance",
    page_icon="👁️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Cyber Minimalist Dark Theme CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
    
    .stApp {
        background-color: #090a0f;
        font-family: 'Space Grotesk', -apple-system, sans-serif;
    }
    
    header[data-testid="stHeader"] {
        background: transparent;
    }
    
    .brand-title {
        font-family: 'Space Grotesk', sans-serif;
        font-size: 1.8rem;
        font-weight: 800;
        letter-spacing: -0.5px;
        color: #ffffff;
        margin-bottom: 2px;
    }
    
    .brand-sub {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.8rem;
        color: #22c55e;
        letter-spacing: 0.1em;
        margin-bottom: 20px;
    }
    
    .stat-box {
        background: #11131a;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 10px;
        padding: 12px 14px;
        text-align: center;
    }
    .stat-val {
        font-family: 'Space Grotesk', sans-serif;
        font-size: 1.5rem;
        font-weight: 700;
        color: #f8fafc;
    }
    .stat-lbl {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.72rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .badge-present {
        background: rgba(34, 197, 94, 0.15);
        color: #4ade80;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
        border: 1px solid rgba(34, 197, 94, 0.35);
    }
    
    .badge-absent {
        background: rgba(239, 68, 68, 0.15);
        color: #f87171;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
        border: 1px solid rgba(239, 68, 68, 0.35);
    }
</style>
""", unsafe_allow_html=True)

# Ensure database is initialized
db.init_db()
db.seed_existing_data()

@st.cache_resource
def load_engine():
    return get_face_engine()

with st.spinner("Initializing YuNet + ArcFace Engine..."):
    engine = load_engine()

# --- Sidebar: Session & Controls ---
with st.sidebar:
    st.markdown('<div class="brand-title">AURA // AI Attendance</div>', unsafe_allow_html=True)
    st.markdown('<div class="brand-sub">ARCFACE 512D + YUNET ONNX</div>', unsafe_allow_html=True)
    
    courses = db.get_all_courses()
    course_options = {c["id"]: f"{c['code']} - {c['name']} ({c['branch']})" for c in courses}
    
    if not course_options:
        st.error("No courses found in database.")
        st.stop()
        
    selected_course_id = st.selectbox(
        "Select Course",
        options=list(course_options.keys()),
        format_func=lambda x: course_options[x]
    )
    
    sessions = db.get_sessions_for_course(selected_course_id)
    session_options = {s["id"]: f"{s['session_date']} - {s['title']}" for s in sessions}
    
    if session_options:
        selected_session_id = st.selectbox(
            "Select Session",
            options=list(session_options.keys()),
            format_func=lambda x: session_options[x]
        )
    else:
        st.warning("No sessions for this course yet.")
        selected_session_id = None
        
    with st.expander("➕ Create New Session", expanded=False):
        new_title = st.text_input("Session Title", value=f"Lecture // {datetime.now().strftime('%b %d')}")
        new_date = st.date_input("Date", value=datetime.now())
        new_time = st.time_input("Time", value=datetime.now().time())
        if st.button("Save New Session", type="primary"):
            created_id = db.create_session(
                course_id=selected_course_id,
                title=new_title,
                session_date=new_date.strftime("%Y-%m-%d"),
                session_time=new_time.strftime("%H:%M")
            )
            st.success("Session created!")
            st.rerun()

    st.markdown("---")
    st.markdown("### 📊 Session Stats")
    
    if selected_session_id:
        attendance_records = db.get_session_attendance_list(selected_session_id)
        total_students = len(attendance_records)
        present_count = sum(1 for r in attendance_records if r["status"] == "Present")
        absent_count = total_students - present_count
        rate = int((present_count / total_students * 100)) if total_students > 0 else 0
        
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f'<div class="stat-box"><div class="stat-val">{total_students}</div><div class="stat-lbl">Enrolled</div></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="stat-box" style="margin-top:8px;"><div class="stat-val" style="color:#4ade80;">{present_count}</div><div class="stat-lbl">Present</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="stat-box"><div class="stat-val" style="color:#f87171;">{absent_count}</div><div class="stat-lbl">Absent</div></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="stat-box" style="margin-top:8px;"><div class="stat-val" style="color:#38bdf8;">{rate}%</div><div class="stat-lbl">Rate</div></div>', unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### 📥 Download Reports")
        
        # CSV Export
        df_export = pd.DataFrame([
            {
                "Roll No": r["roll_no"],
                "Student Name": r["name"],
                "Branch": r["branch"],
                "Status": r["status"],
                "Confidence": f"{int(r['confidence'] * 100)}%" if r["confidence"] > 0 else "N/A",
                "Method": r["marked_method"] or "Unmarked",
                "Timestamp": r["marked_at"] or ""
            }
            for r in attendance_records
        ])
        csv_bytes = df_export.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📄 Download Session CSV",
            data=csv_bytes,
            file_name=f"Attendance_Session_{selected_session_id}.csv",
            mime="text/csv"
        )
        
        # Download Presentation & Math Guide
        ppt_path = "AI_Classroom_Attendance_Presentation_Updated.pptx"
        if os.path.exists(ppt_path):
            with open(ppt_path, "rb") as f:
                st.download_button("📊 Download Project Presentation (PPTX)", data=f.read(), file_name="AURA_Presentation.pptx")
                
        pdf_path = "AI_Classroom_Attendance_Math_and_ML_Guide.pdf"
        if os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                st.download_button("📐 Download Math & ML Guide (PDF)", data=f.read(), file_name="AURA_Math_and_ML_Guide.pdf")

# --- Main Tabs ---
tab_group, tab_camera, tab_portal, tab_students = st.tabs([
    "📸 Classroom Group Photo AI",
    "📱 Live Camera Capture",
    "🎓 Student Portal",
    "👥 Enrolled Students"
])

# ================= TAB 1: GROUP PHOTO AI ================= #
with tab_group:
    st.subheader("Classroom Group Photo AI Recognition")
    st.markdown("Upload wide-angle classroom photos or test with the pre-loaded 35-student classroom benchmark photo.")
    
    col_ctrl, col_slider = st.columns([2, 1])
    with col_ctrl:
        demo_clicked = st.button("✨ Load Pre-Loaded 35-Student Demo Photo", type="primary", use_container_width=True)
        uploaded_file = st.file_uploader("Or Upload Custom Classroom Photo", type=["jpg", "jpeg", "png", "webp"])
    with col_slider:
        threshold = st.slider(
            "Match Sensitivity (Cosine Threshold)",
            min_value=0.30,
            max_value=0.50,
            value=0.35,
            step=0.01,
            help="Threshold for ArcFace cosine similarity. 0.35 is optimal for large lecture halls."
        )

    image_to_process = None
    if demo_clicked:
        sample_path = "test_images/industry_class_photo.jpeg"
        if os.path.exists(sample_path):
            image_to_process = cv2.imread(sample_path)
            st.session_state["active_image"] = image_to_process
            st.session_state["image_name"] = "industry_class_photo.jpeg"
            st.success("Loaded demo classroom photo (industry_class_photo.jpeg)")
    elif uploaded_file is not None:
        file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
        image_to_process = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        st.session_state["active_image"] = image_to_process
        st.session_state["image_name"] = uploaded_file.name

    if "active_image" in st.session_state and st.session_state["active_image"] is not None:
        img_bgr = st.session_state["active_image"]
        
        btn_scan = st.button("🚀 Scan & Identify Faces in Photo", type="primary", use_container_width=True)
        
        if btn_scan:
            if not selected_session_id:
                st.error("Please select a session from the sidebar first!")
            else:
                with st.spinner("Detecting faces with YuNet and extracting ArcFace 512D embeddings..."):
                    known_emb, known_ids, id_meta = db.get_registered_embeddings_for_session(selected_session_id)
                    
                    dets, _ = engine.recognize_faces_in_image(
                        img_bgr,
                        known_embeddings=known_emb,
                        known_student_ids=known_ids,
                        id_meta_map=id_meta,
                        threshold=threshold,
                        draw_annotations=True
                    )
                    
                    matched_map = {}
                    for d in dets:
                        if d.get("is_matched") and d.get("student_id"):
                            sid = d["student_id"]
                            score = d["score"]
                            if sid not in matched_map or score > matched_map[sid]["score"]:
                                matched_map[sid] = {"name": d["name"], "score": score}
                                
                    # Atomic Batch Attendance Update
                    updates = [
                        {"student_id": sid, "status": "Present", "confidence": info["score"], "method": "Group Photo AI"}
                        for sid, info in matched_map.items()
                    ]
                    db.mark_students_attendance_batch(selected_session_id, updates)
                    
                    # Draw annotations for Streamlit display
                    annotated_bgr = img_bgr.copy()
                    h, w = annotated_bgr.shape[:2]
                    for d in dets:
                        bx, by, bw, bh = d["bbox"]
                        color = (34, 197, 94) if d["is_matched"] else (68, 68, 239)
                        cv2.rectangle(annotated_bgr, (bx, by), (bx + bw, by + bh), color, 2)
                        label = f"{d['name']} ({int(d['score']*100)}%)" if d["is_matched"] else "Unknown"
                        cv2.putText(annotated_bgr, label, (bx, max(15, by - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)
                        
                    st.session_state["annotated_view"] = cv2.cvtColor(annotated_bgr, cv2.COLOR_BGR2RGB)
                    st.session_state["dets"] = dets
                    st.session_state["matched_count"] = len(matched_map)
                    st.session_state["matched_names"] = sorted([m["name"] for m in matched_map.values()])
                    st.success(f"Successfully processed! Detected {len(dets)} faces, matched {len(matched_map)} enrolled students.")

        col_img, col_info = st.columns([2, 1])
        with col_img:
            display_img = st.session_state.get("annotated_view", cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
            st.image(display_img, caption="Classroom Detection View", use_container_width=True)
            
        with col_info:
            if "dets" in st.session_state:
                st.markdown("#### Recognition Summary")
                st.metric("Total Faces Detected", len(st.session_state["dets"]))
                st.metric("Enrolled Matched", st.session_state["matched_count"])
                
                if st.session_state["matched_names"]:
                    st.markdown("**Identified Students:**")
                    for name in st.session_state["matched_names"]:
                        st.markdown(f"- ✅ **{name}**")
                else:
                    st.info("No enrolled students matched the current threshold.")

    # Live Roster View
    if selected_session_id:
        st.markdown("---")
        st.subheader("Session Attendance Roster")
        records = db.get_session_attendance_list(selected_session_id)
        
        # Sort absent to top
        records_sorted = sorted(records, key=lambda x: (x["status"] == "Present", x["roll_no"]))
        
        roster_df = pd.DataFrame([
            {
                "Roll No": r["roll_no"],
                "Student Name": r["name"],
                "Branch": r["branch"],
                "Status": "✅ Present" if r["status"] == "Present" else "❌ Absent",
                "Confidence": f"{int(r['confidence'] * 100)}%" if r["confidence"] > 0 else "N/A",
                "Method": r["marked_method"] or "Initial"
            }
            for r in records_sorted
        ])
        
        st.dataframe(roster_df, use_container_width=True, hide_index=True)

# ================= TAB 2: LIVE CAMERA CAPTURE ================= #
with tab_camera:
    st.subheader("Live Camera Attendance")
    st.markdown("Capture a live frame from your phone camera or laptop webcam for instant identification.")
    
    camera_photo = st.camera_input("Take Live Attendance Photo")
    if camera_photo is not None:
        file_bytes = np.asarray(bytearray(camera_photo.read()), dtype=np.uint8)
        live_bgr = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        
        if not selected_session_id:
            st.error("Please select a session from the sidebar first!")
        else:
            with st.spinner("Recognizing faces..."):
                known_emb, known_ids, id_meta = db.get_registered_embeddings_for_session(selected_session_id)
                dets, _ = engine.recognize_faces_in_image(
                    live_bgr,
                    known_embeddings=known_emb,
                    known_student_ids=known_ids,
                    id_meta_map=id_meta,
                    threshold=0.35,
                    draw_annotations=True
                )
                
                for d in dets:
                    if d.get("is_matched") and d.get("student_id"):
                        db.mark_student_attendance(
                            session_id=selected_session_id,
                            student_id=d["student_id"],
                            status="Present",
                            confidence=d["score"],
                            method="Camera AI"
                        )
                        
                annotated_live = live_bgr.copy()
                for d in dets:
                    bx, by, bw, bh = d["bbox"]
                    color = (34, 197, 94) if d["is_matched"] else (68, 68, 239)
                    cv2.rectangle(annotated_live, (bx, by), (bx + bw, by + bh), color, 2)
                    label = f"{d['name']} ({int(d['score']*100)}%)" if d["is_matched"] else "Unknown"
                    cv2.putText(annotated_live, label, (bx, max(15, by - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                    
                st.image(cv2.cvtColor(annotated_live, cv2.COLOR_BGR2RGB), caption="Live Recognized Output", use_container_width=True)
                st.success("Attendance updated from live capture!")

# ================= TAB 3: STUDENT PORTAL ================= #
with tab_portal:
    st.subheader("Student Self-Service Portal")
    st.markdown("Search individual attendance history, percentage, and 75% exam eligibility.")
    
    search_roll = st.text_input("Enter Student Roll Number (e.g., 124CS0078, 124AD0029, 124ME0019):", value="124CS0078")
    if search_roll:
        stats = db.get_student_portal_stats(search_roll.strip())
        if stats:
            st.markdown(f"### Student: **{stats['name']}** ({stats['roll_no']}) - Branch: **{stats['branch']}**")
            
            p_col1, p_col2, p_col3, p_col4 = st.columns(4)
            p_col1.metric("Overall Percentage", f"{stats['overall_percentage']}%")
            p_col2.metric("Classes Attended", stats["total_attended"])
            p_col3.metric("Total Classes", stats["total_sessions"])
            p_col4.metric("Exam Eligibility", "ELIGIBLE" if stats["is_eligible"] else "SHORTAGE")
            
            st.markdown("#### Course-Wise Attendance")
            courses_df = pd.DataFrame(stats["courses"])
            st.dataframe(courses_df, use_container_width=True, hide_index=True)
            
            st.markdown("#### Recent Sessions History")
            history_df = pd.DataFrame(stats["history"])
            st.dataframe(history_df, use_container_width=True, hide_index=True)
        else:
            st.warning(f"No student found with Roll No: {search_roll}")

# ================= TAB 4: ENROLLED STUDENTS ================= #
with tab_students:
    st.subheader("Enrolled Student Database")
    all_students = db.get_all_students_with_courses()
    st.info(f"Total Enrolled Students: {len(all_students)} across 4 Academic Branches (CSE, AI&DS, Mech, ECE)")
    
    student_records = []
    for s in all_students:
        student_records.append({
            "Roll No": s["roll_no"],
            "Name": s["name"],
            "Branch": s["branch"],
            "Enrolled Courses": s["courses"],
            "Vectors": s["vector_count"],
            "Registered On": s["registered_at"]
        })
    st.dataframe(pd.DataFrame(student_records), use_container_width=True, hide_index=True)
