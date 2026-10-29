"""
AURA - Mathematical & Machine Learning Foundations
Pedagogical Technical PDF Document Generator
Built using ReportLab 5.x
"""

import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute total pages and add header/footer."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))

        # Header (Pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, 750, "AURA Technical Guide: Mathematics, ML & Engineering Chronology")
            self.drawRightString(612 - 54, 750, "OpenCV YuNet & InsightFace ArcFace")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.6)
            self.line(54, 744, 612 - 54, 744)

        # Footer (All pages)
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.6)
        self.line(54, 45, 612 - 54, 45)
        self.drawString(54, 32, "AI & Data Science (AI&DS) Technical Teaching & Engineering Document")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(612 - 54, 32, page_str)
        self.restoreState()

def create_teaching_pdf(filename="AI_Classroom_Attendance_Math_and_ML_Guide.pdf"):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    # Custom Clean Academic Typography Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=25,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=6
    )

    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10.5,
        leading=15,
        textColor=colors.HexColor("#334155"),
        spaceAfter=14
    )

    meta_style = ParagraphStyle(
        'DocMeta',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#2563EB"),
        spaceAfter=14
    )

    h1_style = ParagraphStyle(
        'SectionH1',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=12.5,
        leading=16,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'SectionH2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#1E3A8A"),
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'BodyTextCustom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13.5,
        textColor=colors.HexColor("#1E293B"),
        alignment=TA_JUSTIFY,
        spaceAfter=7
    )

    bullet_style = ParagraphStyle(
        'BulletCustom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13.5,
        textColor=colors.HexColor("#1E293B"),
        leftIndent=14,
        spaceAfter=4
    )

    formula_style = ParagraphStyle(
        'FormulaBox',
        parent=styles['Normal'],
        fontName='Courier-Bold',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#0F172A"),
        alignment=TA_CENTER,
        spaceBefore=4,
        spaceAfter=6
    )

    callout_style = ParagraphStyle(
        'CalloutText',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8.5,
        leading=12.5,
        textColor=colors.HexColor("#0F766E")
    )

    story = []

    # Document Header
    story.append(Paragraph("AURA // MATHEMATICAL, ML & ENGINEERING FOUNDATIONS", meta_style))
    story.append(Paragraph("Automated Classroom Attendance: Foundations, Metric Learning & Engineering Problem-Solving", title_style))
    story.append(Paragraph("A Comprehensive Pedagogical Guide to Hyperspherical ArcFace Embeddings, Anchor-Free CNNs, Multi-Scale IoM Deduplication, and Mobile Edge Optimization", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2563EB"), spaceAfter=12))

    # Abstract Callout Box
    abstract_text = (
        "<b>Executive Summary & Pedagogical Scope:</b> This technical document provides both a rigorous mathematical "
        "exposition and an empirical engineering chronicle of the AURA platform. It covers: (1) discrete roll call time "
        "complexity modeling vs. open-set facial verification, (2) OpenCV YuNet anchor-free spatial detection and GIoU loss, "
        "(3) SVD-based affine Procrustes alignment, (4) InsightFace ArcFace additive angular margin on the 512D hypersphere, "
        "(5) high-throughput cosine matrix verification, and (6) in-depth case studies of real-world edge challenges "
        "(including the 'Krishna Agarwal' hubness false positive cascade, Android 48MP resolution explosion, and multi-scale anchor dual boxes)."
    )
    callout_data = [[Paragraph(abstract_text, callout_style)]]
    callout_table = Table(callout_data, colWidths=[504])
    callout_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F0FDFA")),
        ('BORDER', (0,0), (-1,-1), 1, colors.HexColor("#0D9488")),
        ('TOPPADDING', (0,0), (-1,-1), 7),
        ('BOTTOMPADDING', (0,0), (-1,-1), 7),
        ('LEFTPADDING', (0,0), (-1,-1), 9),
        ('RIGHTPADDING', (0,0), (-1,-1), 9),
    ]))
    story.append(callout_table)
    story.append(Spacer(1, 10))

    # SECTION 1
    story.append(Paragraph("1. Problem Modeling: Discrete Roll Calls vs. Continuous Biometric Verification", h1_style))
    story.append(Paragraph(
        "Traditional classroom attendance relies on discrete human sampling—either vocal roll-calling or paper sign-in rosters. "
        "Formally, consider a course enrollment set <i>S = {s<sub>1</sub>, s<sub>2</sub>, ..., s<sub>K</sub>}</i> of <i>K</i> students. "
        "Manual roll calling represents a linear search <i>O(K)</i> executed at an average human latency of <i>t<sub>call</sub> ≈ 8 s</i> per student. "
        "For a classroom of <i>K = 100</i>, total instructional time expenditure reaches:", body_style
    ))
    story.append(Paragraph("T<sub>manual</sub> = Σ<sub>i=1</sub><sup>K</sup> t<sub>call</sub>(s<sub>i</sub>) ≈ 100 × 8 s = 800 s ≈ 13.3 minutes", formula_style))
    story.append(Paragraph(
        "Over a standard university semester of <i>N<sub>sessions</sub> = 40</i> lectures, cumulative lost instructional time exceeds <b>8.8 hours</b>. "
        "Furthermore, paper roll sheets provide zero cryptographic authentication, exhibiting an empirical proxy vulnerability rate exceeding 15%. "
        "AURA models attendance as an optimal open-set facial verification problem over an optical image frame <i>I ∈ ℝ<sup>H × W × 3</sup></i>:", body_style
    ))
    story.append(Paragraph("f: I → 𝒱 = {(b<sub>k</sub>, y<sub>k</sub>, s<sub>k</sub>)}<sub>k=1</sub><sup>M</sup>,   y<sub>k</sub> ∈ S ∪ {Unknown}", formula_style))
    story.append(Paragraph(
        "where <i>M</i> is the number of detected faces, <i>b<sub>k</sub> = (x, y, w, h)</i> is the bounding box coordinates, "
        "<i>y<sub>k</sub></i> is the identified enrolled student (or Unknown), and <i>s<sub>k</sub> ∈ [0, 1]</i> is the cosine confidence score.", body_style
    ))

    # SECTION 2
    story.append(Paragraph("2. OpenCV YuNet: Anchor-Free CNN Multi-Scale Face Detection", h1_style))
    story.append(Paragraph(
        "YuNet is an ultra-lightweight, anchor-free convolutional neural network designed specifically for real-time edge face detection. "
        "Unlike legacy anchor-based detectors (e.g., RetinaFace, Faster R-CNN) that evaluate dense geometric anchor priors across multiple scales "
        "(incurring high computational overhead), YuNet operates directly on feature map grid points.", body_style
    ))

    story.append(Paragraph("2.1 Anchor-Free Spatial Regression & Generalized IoU Loss", h2_style))
    story.append(Paragraph(
        "For each feature pyramid grid location <i>(x<sub>g</sub>, y<sub>g</sub>)</i>, YuNet predicts a 4-dimensional bounding box distance tuple "
        "<i>(l, t, r, b)</i> representing offsets to the left, top, right, and bottom boundaries. "
        "To ensure scale-invariant gradient descent, bounding box regression is optimized using Generalized Intersection over Union (GIoU) loss:", body_style
    ))
    story.append(Paragraph("ℒ<sub>GIoU</sub> = 1 - IoU(B, B̂) + |C \\ (B ∪ B̂)| / |C|", formula_style))
    story.append(Paragraph(
        "where <i>B</i> is the ground truth bounding box, <i>B̂</i> is the predicted bounding box, and <i>C</i> is the smallest convex hull enclosing both <i>B</i> and <i>B̂</i>. "
        "GIoU solves the vanishing gradient limitation of standard IoU when predicted and target boxes do not overlap, providing continuous smooth gradients.", body_style
    ))

    story.append(Paragraph("2.2 5-Point Facial Landmark Regression", h2_style))
    story.append(Paragraph(
        "Simultaneously, YuNet regresses 5 primary facial landmarks: left eye <i>p<sub>1</sub></i>, right eye <i>p<sub>2</sub></i>, nose tip <i>p<sub>3</sub></i>, "
        "left mouth corner <i>p<sub>4</sub></i>, and right mouth corner <i>p<sub>5</sub></i> using smooth L1 loss:", body_style
    ))
    story.append(Paragraph("ℒ<sub>lmk</sub> = Σ<sub>i=1</sub><sup>5</sup> smooth<sub>L1</sub>(p<sub>i</sub> - p̂<sub>i</sub>)", formula_style))
    story.append(Paragraph(
        "These 5 landmarks are critical for decoupling head pose, camera tilt, and in-plane perspective distortions prior to identity verification.", body_style
    ))

    # SECTION 3
    story.append(Paragraph("3. Geometric Affine Normalization & SVD Procrustes Alignment", h1_style))
    story.append(Paragraph(
        "Raw face crops exhibit substantial pitch, yaw, roll, and distance variations. Feeding unaligned face patches directly into a deep metric recognizer "
        "drastically degrades inter-class discriminability. AURA normalizes all detected faces onto a standardized canonical 112 × 112 coordinate frame using an optimal affine transformation.", body_style
    ))
    story.append(Paragraph(
        "Let <b>P</b> = {p<sub>i</sub>}<sub>i=1</sub><sup>5</sup> be the observed landmarks and <b>Q</b> = {q<sub>i</sub>}<sub>i=1</sub><sup>5</sup> be the canonical frontal facial template coordinates. "
        "We seek an affine similarity transformation matrix <i>T ∈ ℝ<sup>2 × 3</sup></i> minimizing the Procrustes Euclidean landmark residual:", body_style
    ))
    story.append(Paragraph("min<sub>T</sub> Σ<sub>i=1</sub><sup>5</sup> || T · [p<sub>i</sub>, 1]<sup>T</sup> - q<sub>i</sub> ||<sup>2</sup>", formula_style))
    story.append(Paragraph(
        "Using Singular Value Decomposition (SVD) of the centered covariance matrix <i>Σ<sub>PQ</sub> = P<sup>T</sup> Q = U D V<sup>T</sup></i>, "
        "the optimal rotation is solved as <i>R = U V<sup>T</sup></i>. Once <i>T</i> is computed, bilinear spatial interpolation maps the pixel grid "
        "into the canonical frontal patch <i>I<sub>aligned</sub> ∈ ℝ<sup>112 × 112 × 3</sup></i>.", body_style
    ))

    # SECTION 4
    story.append(Paragraph("4. InsightFace ArcFace: Additive Angular Margin Loss on a Hypersphere", h1_style))
    story.append(Paragraph(
        "The machine learning backbone of AURA is the ArcFace (ResNet-50) deep convolutional neural network. "
        "ArcFace reformulates feature learning entirely on the surface of a unit hypersphere <i>S<sup>d-1</sup></i> in ℝ<sup>d</sup> (where <i>d = 512</i>). "
        "Both the class weight vectors <i>W<sub>j</sub></i> and feature embeddings <i>x<sub>i</sub></i> are ℓ<sub>2</sub>-normalized:", body_style
    ))
    story.append(Paragraph("||W<sub>j</sub>||<sub>2</sub> = 1,     ||x<sub>i</sub>||<sub>2</sub> = 1   ⇒   W<sub>j</sub><sup>T</sup> x<sub>i</sub> = cos(θ<sub>j</sub>)", formula_style))
    story.append(Paragraph(
        "where <i>θ<sub>j</sub></i> is the geometric angle between feature vector <i>x<sub>i</sub></i> and class centroid <i>W<sub>j</sub></i> on the hypersphere. "
        "To enforce an explicit angular decision boundary, ArcFace injects an additive angular margin penalty <i>m</i> directly into the target angle <i>θ<sub>y<sub>i</sub></sub></i>:", body_style
    ))
    story.append(Paragraph(
        "ℒ<sub>ArcFace</sub> = - (1/N) Σ<sub>i=1</sub><sup>N</sup> log [ e<sup>s·cos(θ<sub>y<sub>i</sub></sub> + m)</sup> / ( e<sup>s·cos(θ<sub>y<sub>i</sub></sub> + m)</sup> + Σ<sub>j ≠ y<sub>i</sub></sub> e<sup>s·cos(θ<sub>j</sub>)</sup> ) ]",
        formula_style
    ))
    story.append(Paragraph(
        "where <b>s = 64</b> is the feature scaling radius and <b>m = 0.5 rad (≈ 28.6°)</b> is the additive angular margin penalty, "
        "guaranteeing strict intra-class geodesic concentration and maximizing inter-class separation.", body_style
    ))

    # Loss Table Comparison
    loss_table_data = [
        ["Loss Function", "Metric Formulation", "Decision Boundary", "Intra-Class Geometry"],
        ["Softmax", "W^T x = ||W||||x|| cos θ", "W_1^T x = W_2^T x", "High variance / scattered"],
        ["SphereFace", "cos(m·θ)", "cos(m·θ_1) = cos(θ_2)", "Multiplicative margin (unstable)"],
        ["CosFace", "cos(θ) - m", "cos(θ_1) - m = cos(θ_2)", "Cosine margin (linear)"],
        ["ArcFace (AURA)", "cos(θ + m)", "cos(θ_1 + m) = cos(θ_2)", "Exact geodesic angular margin"]
    ]
    t_loss = Table(loss_table_data, colWidths=[90, 140, 140, 134])
    t_loss.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E3A8A")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_loss)
    story.append(Spacer(1, 10))

    # SECTION 5
    story.append(Paragraph("5. Vector Verification & Cosine Matrix Matching", h1_style))
    story.append(Paragraph(
        "During live inference, ArcFace maps any normalized aligned face crop <i>I<sub>aligned</sub></i> into a unit vector embedding <i>e ∈ ℝ<sup>512</sup></i>, "
        "such that ||e||<sub>2</sub> = 1. The degree of biometric similarity between a probe face <i>e<sub>probe</sub></i> and an enrolled student vector <i>e<sub>gallery</sub></i> "
        "simplifies to their vector dot product:", body_style
    ))
    story.append(Paragraph("sim(e<sub>probe</sub>, e<sub>gallery</sub>) = e<sub>probe</sub> · e<sub>gallery</sub> = e<sub>probe</sub><sup>T</sup> e<sub>gallery</sub>", formula_style))
    story.append(Paragraph(
        "For a classroom course with <i>K</i> enrolled embedding vectors, all registered embeddings are stacked into a matrix <i>E<sub>gallery</sub> ∈ ℝ<sup>K × 512</sup></i>. "
        "When an optical frame containing <i>M</i> detected students is processed, the probe matrix <i>P ∈ ℝ<sup>M × 512</sup></i> computes all pairwise similarities simultaneously via a single BLAS GEMM matrix multiplication:", body_style
    ))
    story.append(Paragraph("S = P · E<sub>gallery</sub><sup>T</sup>  ∈  ℝ<sup>M × K</sup>", formula_style))
    story.append(Paragraph(
        "On modern Intel/AMD CPU hardware with AVX-512 extensions, computing <i>S</i> for <i>M = 100</i> faces and <i>K = 500</i> enrolled vectors resolves in less than <b>3.2 ms</b>.", body_style
    ))

    # SECTION 6 - CASE STUDY: KRISHNA AGARWAL HUBNESS
    story.append(Paragraph("6. Case Study 1: The 'Krishna Agarwal' False Positive Cascade (Hubness Failure)", h1_style))
    story.append(Paragraph(
        "During mobile phone attendance testing, an unexpected phenomenon occurred: multiple unrelated students and strangers were repeatedly "
        "misclassified as enrolled student <b>Krishna Agarwal</b> with match confidence exceeding 60%. Systematic debugging revealed a classic failure mode in deep metric learning known as the <b>Hubness Problem</b>.", body_style
    ))

    story.append(Paragraph("6.1 Root Cause: The Area-Only Registration Trap", h2_style))
    story.append(Paragraph(
        "When Krishna was initially enrolled from a phone photo, YuNet localized two bounding boxes:<br/>"
        "• <b>Face 0 (Real Face)</b>: Confidence = 0.914, Bounding Box = [140, 471, 219, 312], Area = 68,328 px<sup>2</sup>.<br/>"
        "• <b>Face 1 (Shirt Collar / Neck)</b>: Confidence = 0.594, Bounding Box = [248, 708, 320, 376], Area = 120,320 px<sup>2</sup>.<br/>"
        "Because the enrollment code previously selected the primary face purely by bounding box area <i>w × h</i>, it selected the non-face collar patch!", body_style
    ))

    story.append(Paragraph("6.2 Hyperspherical Collapse to a Central Hub Vector", h2_style))
    story.append(Paragraph(
        "When a non-face image patch is passed into an ArcFace network trained exclusively on human faces, the lack of distinct facial landmarks causes the intermediate feature maps "
        "to collapse toward the global feature centroid on <i>S<sup>511</sup></i>. In high-dimensional metric space, such a collapsed vector acts as a <b>'Hub Vector'</b>: "
        "it possesses high cosine similarity (0.45 to 0.64) with a broad distribution of unrelated face embeddings. On a 114-student classroom benchmark photo, this single corrupted embedding matched <b>16 random strangers</b> above the threshold!", body_style
    ))

    story.append(Paragraph("6.3 The Mathematical Solution: Multi-Factor Face Quality & Ensemble Scoring", h2_style))
    story.append(Paragraph(
        "Two structural defenses were engineered to permanently eradicate hubness vulnerabilities:<br/>"
        "1. <b>Multi-Factor Face Quality Metric</b>: Candidate selection now combines confidence, centrality, and scale:<br/>", body_style
    ))
    story.append(Paragraph("Quality(f) = (conf)<sup>2</sup> × [1 - dist(center<sub>face</sub>, center<sub>image</sub>)] × √(Area / Area<sub>image</sub>)", formula_style))
    story.append(Paragraph(
        "2. <b>Ensemble Student-Level Pooling</b>: For students with multiple reference photos, similarity is no longer determined by a vulnerable single maximum. "
        "Instead, the engine computes a blended ensemble of the top-2 similarities:<br/>", body_style
    ))
    story.append(Paragraph("Score<sub>ensemble</sub> = 0.75 · s<sub>top1</sub> + 0.25 · s<sub>top2</sub>", formula_style))
    story.append(Paragraph(
        "If a single embedding produces an outlier match while the student's other photos show zero correlation (s<sub>top2</sub> < 0.15), the match is penalized and rejected. "
        "Following database re-extraction, false positive matches on the 114-face classroom photo dropped from 16 to exactly <b>0</b>.", body_style
    ))

    # SECTION 7 - MOBILE EDGE OPTIMIZATION
    story.append(Paragraph("7. Case Study 2: Android 48MP Resolution Explosion & Web Security", h1_style))
    story.append(Paragraph(
        "While laptop webcam attendance functioned smoothly, testing from mobile devices revealed two platform-specific disparities: "
        "(1) high mobile camera resolution causing neural network saturation, and (2) browser camera permission blocks.", body_style
    ))

    story.append(Paragraph("7.1 Receptive Field Saturation at 4000 × 3000 Resolution", h2_style))
    story.append(Paragraph(
        "Modern smartphones capture native photos at 12MP to 48MP (e.g. 4000 × 3000). When fed into YuNet without preprocessing, "
        "the convolutional receptive fields saturated. Benchmark tests revealed that a 4000 × 3000 input caused YuNet to detect <b>11 phantom faces</b> on a single individual, "
        "with inference latency surging from 73 ms to <b>1131 ms</b>. Rescaling the image to a standardized maximum dimension of 1600 px restored clean detection (1 face) and dropped latency to <b>138 ms</b>.", body_style
    ))

    story.append(Paragraph("7.2 Client-Side Canvas Pre-Compression", h2_style))
    story.append(Paragraph(
        "Uploading raw 15 MB mobile photos exhausted mobile browser RAM and created 5–8 second Wi-Fi transfer delays. "
        "A client-side HTML5 canvas optimizer (<i>optimizeImageForUpload</i>) was integrated into the frontend. Photos are downscaled to 1600 px client-side before transmission, "
        "cutting network payload to ~350 KB, normalizing EXIF orientation, and reducing transfer time to <b>< 100 ms</b>.", body_style
    ))

    story.append(Paragraph("7.3 Chromium W3C Insecure Origin Policy", h2_style))
    story.append(Paragraph(
        "On Android Chrome, accessing the server over LAN HTTP (e.g. <i>http://192.168.x.x:8000</i>) strictly disables <i>navigator.mediaDevices.getUserMedia</i>. "
        "The web interface was enhanced with defensive detection: on mobile HTTP, the UI automatically routes users to <b>Group Photo AI Upload</b>, "
        "where native camera inputs (<i>capture='environment'</i>) operate unrestricted with 1-tap capture speed.", body_style
    ))

    # SECTION 8 - MULTI-SCALE OVERLAP & IOM
    story.append(Paragraph("8. Case Study 3: Dual Bounding Boxes on Close-Up Faces & IoM Deduplication", h1_style))
    story.append(Paragraph(
        "When students took close-up selfie portraits occupying >50% of the camera frame, the UI rendered <b>two overlapping green boxes</b> on the same face (e.g., Aman 48% on upper face, Aman 47% on lower face).", body_style
    ))

    story.append(Paragraph("8.1 Feature Pyramid Anchor Grid Collision", h2_style))
    story.append(Paragraph(
        "On large faces, adjacent Feature Pyramid Network (FPN) levels in YuNet simultaneously detected overlapping sub-regions: Anchor level <i>P<sub>4</sub></i> localized the forehead and eyes, "
        "while level <i>P<sub>5</sub></i> localized the eyes, nose, and mouth. Because the vertical shift between the two boxes reduced their standard IoU to ~18%, "
        "standard Non-Maximum Suppression (NMS threshold = 0.30) treated them as two separate people.", body_style
    ))

    story.append(Paragraph("8.2 Intersection over Minimum (IoM) Suppression Formulation", h2_style))
    story.append(Paragraph(
        "To resolve multi-scale anchor collisions, AURA introduced an <b>Intersection over Minimum (IoM)</b> suppression filter:", body_style
    ))
    story.append(Paragraph("IoM(B<sub>1</sub>, B<sub>2</sub>) = Area(B<sub>1</sub> ∩ B<sub>2</sub>) / min(Area(B<sub>1</sub>), Area(B<sub>2</sub>))", formula_style))
    story.append(Paragraph(
        "If <i>IoM(B<sub>1</sub>, B<sub>2</sub>) > 0.30</i>, the detector recognizes that the smaller box is substantially enclosed within the larger face region, "
        "suppressing the duplicate. In addition, an identity constraint enforces that a single enrolled student cannot possess two overlapping detections, "
        "guaranteeing exactly <b>one clean box</b> per student.", body_style
    ))

    # SECTION 9 - PROBLEM CHRONOLOGY TABLE
    story.append(Paragraph("9. Complete Engineering Problem-Solving Chronology", h1_style))
    story.append(Paragraph(
        "The following matrix summarizes the key engineering hurdles encountered throughout the project lifecycle, their theoretical root causes, and the deployed production fixes:", body_style
    ))

    problem_table_data = [
        ["Hurdle", "Manifestation", "Root Cause", "Engineering Solution"],
        ["1. Windows Locks", "Errno 13 Permission Denied on PPTX", "PowerPoint exclusively locks open files on OS level", "Dynamic timestamped file generation & FastAPI streaming"],
        ["2. Console Crash", "UnicodeEncodeError on cp1252 terminal", "Windows console fails on special characters like checkmarks", "Clean ASCII logging tags ([MATCH], [UNKNOWN])"],
        ["3. Portrait Drop", "Divyansh registration rejected (400)", "Phone EXIF rotation tilt & multi-face background rejection", "ImageOps.exif_transpose + 360° fallback rotation search"],
        ["4. Hubness Storm", "Strangers classified as Krishna Agarwal", "Area-only sort picked collar patch; ArcFace collapsed to hub", "Multi-factor quality metric + Top-2 ensemble pooling"],
        ["5. Mobile Bloat", "Phone UI lag; 11 phantom detections", "4000x3000 native phone resolution saturated YuNet anchors", "Client-side canvas compression + backend 1600px guard"],
        ["6. Dual Box Bug", "Two overlapping boxes on close-up face", "FPN multi-scale anchors fired; vertical shift evaded IoU", "Intersection over Minimum (IoM > 0.30) deduplication"]
    ]
    t_prob = Table(problem_table_data, colWidths=[80, 130, 140, 154])
    t_prob.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0F172A")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0,0), (-1,-1), 4.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4.5),
    ]))
    story.append(t_prob)
    story.append(Spacer(1, 12))

    # SECTION 10 - SUMMARY
    story.append(Paragraph("10. Pedagogical Takeaways & Production Guidelines", h1_style))
    summary_items = [
        "<b>Metric Learning Quality Dictates Accuracy:</b> A deep embedding space is only as good as the crops registered into it. Strict quality scoring on registration photos is essential to prevent hubness collapse.",
        "<b>Anchor Scales Must Match Receptive Fields:</b> Feeding ultra-high-resolution images (e.g. 48MP) into standard face detectors degrades both speed and accuracy; input normalization is mandatory.",
        "<b>IoM Trumps IoU on Large Objects:</b> Standard IoU fails when detectors output shifted sub-components of large objects. Intersection over Minimum (IoM) is the mathematically correct metric for multi-scale containment.",
        "<b>Edge Defense-in-Depth:</b> Combining client-side image compression, server-side dimension guards, and ensemble vector verification yields sub-second classroom attendance that is robust across laptops and mobile phones."
    ]
    for item in summary_items:
        story.append(Paragraph(f"• {item}", bullet_style))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Teaching PDF generated successfully at: {filename}")
    return filename

if __name__ == "__main__":
    create_teaching_pdf()
