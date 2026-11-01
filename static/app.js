/**
 * AURA // AI Classroom Attendance System Frontend Controller
 * v2.4.0 — Mobile/Android fixes, PWA support, custom confirm modal
 */

// ======================= UTILITIES: isMobile ======================= //
const isMobile = /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent);

// ======================= SERVICE WORKER (PWA) ======================= //
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/static/sw.js').catch(() => {});
    });
}

// ======================= PWA Install Prompt ======================= //
let _deferredInstallPrompt = null;
window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    _deferredInstallPrompt = e;
    // Show install banner only on mobile if not already installed
    if (isMobile && !window.matchMedia('(display-mode: standalone)').matches) {
        showPwaInstallBanner();
    }
});

function showPwaInstallBanner() {
    if (document.getElementById('pwa-install-banner')) return;
    const banner = document.createElement('div');
    banner.id = 'pwa-install-banner';
    banner.className = 'pwa-install-banner';
    banner.innerHTML = `
        <span class="pwa-icon">◆</span>
        <div class="pwa-text">
            <strong>Install AURA.AI</strong>
            <small>Add to Home Screen for quick classroom access</small>
        </div>
        <button class="pwa-install-btn" id="pwa-do-install">Install</button>
        <button class="pwa-install-dismiss" id="pwa-dismiss">✕</button>
    `;
    document.body.appendChild(banner);
    document.getElementById('pwa-do-install').addEventListener('click', async () => {
        if (_deferredInstallPrompt) {
            _deferredInstallPrompt.prompt();
            const { outcome } = await _deferredInstallPrompt.userChoice;
            _deferredInstallPrompt = null;
        }
        banner.remove();
    });
    document.getElementById('pwa-dismiss').addEventListener('click', () => banner.remove());
}

// ======================= CUSTOM CONFIRM MODAL ======================= //
// Replaces window.confirm() which is blocked on many Android WebViews

function showConfirm(title, message) {
    return new Promise((resolve) => {
        const modal = document.getElementById('modal-confirm');
        const titleEl = document.getElementById('confirm-modal-title');
        const msgEl = document.getElementById('confirm-modal-message');
        const okBtn = document.getElementById('confirm-modal-ok');
        const cancelBtn = document.getElementById('confirm-modal-cancel');

        if (!modal) {
            // Fallback if modal not in DOM yet
            resolve(window.confirm(message));
            return;
        }

        titleEl.textContent = title;
        msgEl.textContent = message;
        modal.style.display = 'flex';

        const cleanup = () => { modal.style.display = 'none'; };

        const onOk = () => { cleanup(); resolve(true); okBtn.removeEventListener('click', onOk); cancelBtn.removeEventListener('click', onCancel); };
        const onCancel = () => { cleanup(); resolve(false); okBtn.removeEventListener('click', onOk); cancelBtn.removeEventListener('click', onCancel); };

        okBtn.addEventListener('click', onOk);
        cancelBtn.addEventListener('click', onCancel);
    });
}

// ======================= AI SCAN LOADING OVERLAY ======================= //

function showScanOverlay(text = 'SCANNING FACES WITH ARCFACE...') {
    const overlay = document.getElementById('ai-scan-overlay');
    const textEl = document.getElementById('ai-scan-overlay-text');
    const bar = document.getElementById('ai-scan-progress-bar');
    if (!overlay) return;
    if (textEl) textEl.textContent = text;
    overlay.style.display = 'flex';
    if (bar) {
        bar.style.width = '0%';
        // Animate progress bar to simulate processing
        let pct = 0;
        const tick = setInterval(() => {
            pct += Math.random() * 12;
            if (pct >= 92) { clearInterval(tick); pct = 92; }
            bar.style.width = pct + '%';
        }, 400);
        overlay._tickInterval = tick;
    }
}

function hideScanOverlay() {
    const overlay = document.getElementById('ai-scan-overlay');
    const bar = document.getElementById('ai-scan-progress-bar');
    if (!overlay) return;
    if (bar) {
        if (overlay._tickInterval) clearInterval(overlay._tickInterval);
        bar.style.width = '100%';
    }
    setTimeout(() => { overlay.style.display = 'none'; if (bar) bar.style.width = '0%'; }, 350);
}

// ======================= GLOBAL FETCH ERROR HANDLER ======================= //

let _serverOfflineToast = null;
const _origFetch = window.fetch.bind(window);
window.fetch = async function(...args) {
    try {
        const response = await _origFetch(...args);
        if (_serverOfflineToast) { _serverOfflineToast.remove(); _serverOfflineToast = null; }
        return response;
    } catch (err) {
        // Network error — server unreachable
        if (!_serverOfflineToast) {
            _serverOfflineToast = document.createElement('div');
            _serverOfflineToast.className = 'toast error';
            _serverOfflineToast.innerHTML = `<span>✕</span><span>Server unreachable — check WiFi connection</span><button class="toast-retry-btn" onclick="window.location.reload()">Retry</button>`;
            _serverOfflineToast.style.cssText = 'opacity:1; position:fixed; bottom:80px; right:16px; z-index:9999;';
            const container = document.getElementById('toast-container');
            if (container) container.appendChild(_serverOfflineToast);
        }
        throw err;
    }
};

// Application State
const state = {
    currentTab: 'take-attendance',
    selectedSessionId: null,
    courses: [],
    sessions: [],
    students: [],
    selectedGroupFile: null,
    originalGroupPhotoSrc: null,
    annotatedGroupPhotoSrc: null,
    showingAnnotatedGroup: true,
    stagedGroupPhotos: [],
    activeGroupPhotoIndex: 0,
    webcamStream: null,
    webcamInterval: null,
    regCamStream: null,
    regCapturedB64: null,
    webcamFacingMode: 'environment', // Back camera ideal for classrooms
    regFacingMode: 'user', // Selfie camera default for student portrait
    threshold: 0.38,
    webcamScanInterval: 1400,
    boxStyle: 'minimal', // 'minimal' | 'corners' | 'none'
    showNameTags: true,
    showLaser: false,
    autoMark: true,
    liveDetectedTargets: [],
    hudAnimationId: null
};

// DOM Elements
const el = {
    // Navigation & Mobile
    sidebar: document.querySelector('.sidebar'),
    sidebarBackdrop: document.getElementById('sidebar-backdrop'),
    btnMobileMenu: document.getElementById('btn-mobile-menu'),
    btnCloseSidebar: document.getElementById('btn-close-sidebar'),
    mobileIpLink: document.getElementById('mobile-ip-link'),
    navItems: document.querySelectorAll('.nav-item'),
    bottomNavItems: document.querySelectorAll('.bottom-nav-item'),
    tabPanes: document.querySelectorAll('.tab-pane'),
    pageTitle: document.getElementById('page-title'),
    pageSubtitle: document.getElementById('page-subtitle'),
    
    // Quick action
    btnQuickNewSession: document.getElementById('btn-quick-new-session'),
    
    // Attendance Tab
    sessionSelect: document.getElementById('attendance-session-select'),
    statCourseCode: document.getElementById('stat-course-code'),
    statEnrolled: document.getElementById('stat-enrolled'),
    statPresent: document.getElementById('stat-present'),
    statRate: document.getElementById('stat-rate'),
    modeBtns: document.querySelectorAll('.mode-btn'),
    panelGroupPhoto: document.getElementById('mode-panel-group-photo'),
    panelLiveWebcam: document.getElementById('mode-panel-live-webcam'),
    btnExportExcel: document.getElementById('btn-export-excel'),
    btnExportCsv: document.getElementById('btn-export-csv'),
    btnExportCourseExcel: document.getElementById('btn-export-course-excel'),

    // Mobile camera triggers
    btnMobileSnapPhoto: document.getElementById('btn-mobile-snap-photo'),
    btnMobileGalleryPhoto: document.getElementById('btn-mobile-gallery-photo'),
    groupCameraInput: document.getElementById('group-camera-input'),
    btnFlipWebcam: document.getElementById('btn-flip-webcam'),
    
    // Manage Course Roster Modal
    modalManageRoster: document.getElementById('modal-manage-roster'),
    rosterModalTitle: document.getElementById('roster-modal-title'),
    rosterModalSubtitle: document.getElementById('roster-modal-subtitle'),
    btnModalCourseExcel: document.getElementById('btn-modal-course-excel'),
    btnModalCourseCsv: document.getElementById('btn-modal-course-csv'),
    selectUnenrolledStudent: document.getElementById('select-unenrolled-student'),
    btnDoEnrollStudent: document.getElementById('btn-do-enroll-student'),
    courseRosterTbody: document.getElementById('course-roster-tbody'),
    
    // Group Photo
    groupDropzone: document.getElementById('group-dropzone'),
    groupFileInput: document.getElementById('group-file-input'),
    groupPreviewWrapper: document.getElementById('group-preview-wrapper'),
    groupPreviewImg: document.getElementById('group-preview-img'),
    dropzonePrompt: document.getElementById('dropzone-prompt'),
    btnClearGroupImg: document.getElementById('btn-clear-group-img'),
    btnToggleGroupAnnotation: document.getElementById('btn-toggle-group-annotation'),
    btnProcessGroup: document.getElementById('btn-process-group'),
    btnProcessGroupText: document.getElementById('btn-process-group-text'),
    btnAddMoreGroupPhoto: document.getElementById('btn-add-more-group-photo'),
    stagedPhotosCount: document.getElementById('staged-photos-count'),
    stagedThumbnailsRow: document.getElementById('staged-thumbnails-row'),
    aiScanSummary: document.getElementById('ai-scan-summary'),
    scanFacesCount: document.getElementById('scan-faces-count'),
    scanRecognizedNames: document.getElementById('scan-recognized-names'),
    
    // Live Webcam & Futuristic HUD
    webcamVideo: document.getElementById('webcam-video'),
    webcamCanvas: document.getElementById('webcam-canvas'),
    webcamHudCanvas: document.getElementById('webcam-hud-canvas'),
    hudLaserLine: document.getElementById('hud-laser-line'),
    webcamHudStatus: document.getElementById('webcam-hud-status'),
    btnStartWebcam: document.getElementById('btn-start-webcam'),
    btnStopWebcam: document.getElementById('btn-stop-webcam'),
    btnSnapFrame: document.getElementById('btn-snap-frame'),
    tickerTags: document.getElementById('ticker-tags'),
    
    // HUD Controls & Box Options
    btnToggleBoxes: document.getElementById('btn-toggle-boxes'),
    stylePills: document.querySelectorAll('.style-pill'),
    toggleHudLabels: document.getElementById('toggle-hud-labels'),
    toggleHudLaser: document.getElementById('toggle-hud-laser'),
    toggleHudAutoMark: document.getElementById('toggle-hud-automark'),
    speedPills: document.querySelectorAll('.speed-pill'),
    inputHudThreshold: document.getElementById('input-hud-threshold'),
    labelHudThreshold: document.getElementById('label-hud-threshold'),
    
    // Roster Table
    rosterCountLabel: document.getElementById('roster-count-label'),
    rosterAbsentBadge: document.getElementById('roster-absent-badge'),
    rosterPresentBadge: document.getElementById('roster-present-badge'),
    rosterTbody: document.getElementById('roster-tbody'),
    
    // Sessions Tab
    sessionsTableBody: document.getElementById('sessions-table-body'),
    filterSessionCourse: document.getElementById('filter-session-course'),
    btnOpenCreateSessionModal: document.getElementById('btn-open-create-session-modal'),
    modalCreateSession: document.getElementById('modal-create-session'),
    formCreateSession: document.getElementById('form-create-session'),
    newSessionCourse: document.getElementById('new-session-course'),
    newSessionDate: document.getElementById('new-session-date'),
    newSessionTime: document.getElementById('new-session-time'),
    btnAutodetectDatetime: document.getElementById('btn-autodetect-datetime'),
    newSessionTitle: document.getElementById('new-session-title'),
    
    // Student Portal Tab
    studentPortalSearch: document.getElementById('student-portal-search'),
    studentPortalSelect: document.getElementById('student-portal-select'),
    btnFetchStudentStats: document.getElementById('btn-fetch-student-stats'),
    studentResultsView: document.getElementById('student-results-view'),
    portalAvatar: document.getElementById('portal-avatar'),
    portalName: document.getElementById('portal-name'),
    portalRoll: document.getElementById('portal-roll'),
    portalBranch: document.getElementById('portal-branch'),
    portalOverallPct: document.getElementById('portal-overall-pct'),
    portalEligibilityTag: document.getElementById('portal-eligibility-tag'),
    portalCoursesGrid: document.getElementById('portal-courses-grid'),
    portalHistoryTbody: document.getElementById('portal-history-tbody'),
    btnShowStudentQr: document.getElementById('btn-show-student-qr'),
    modalQrCode: document.getElementById('modal-qr-code'),
    qrCodeDisplay: document.getElementById('qr-code-display'),
    qrCodeUrl: document.getElementById('qr-code-url'),
    
    // Registration Tab
    studentRegForm: document.getElementById('student-reg-form'),
    regRoll: document.getElementById('reg-roll'),
    regName: document.getElementById('reg-name'),
    regBranch: document.getElementById('reg-branch'),
    btnSrcUpload: document.getElementById('btn-src-upload'),
    btnSrcCamera: document.getElementById('btn-src-camera'),
    srcUploadBox: document.getElementById('src-upload-box'),
    srcCameraBox: document.getElementById('src-camera-box'),
    regPhotoFile: document.getElementById('reg-photo-file'),
    regCamVideo: document.getElementById('reg-cam-video'),
    regCamCanvas: document.getElementById('reg-cam-canvas'),
    btnRegSnap: document.getElementById('btn-reg-snap'),
    btnRegFlipCamera: document.getElementById('btn-reg-flip-camera'),
    regPreviewBox: document.getElementById('reg-preview-box'),
    regPreviewLabel: document.getElementById('reg-preview-label'),
    regPhotosGallery: document.getElementById('reg-photos-gallery'),
    btnClearRegPhotos: document.getElementById('btn-clear-reg-photos'),
    registeredStudentsList: document.getElementById('registered-students-list'),
    totalRegisteredBadge: document.getElementById('total-registered-badge'),

    // Add Extra Photos Modal
    modalAddPhotos: document.getElementById('modal-add-photos'),
    formAddPhotos: document.getElementById('form-add-photos'),
    addPhotosStudentId: document.getElementById('add-photos-student-id'),
    addPhotosModalTitle: document.getElementById('add-photos-modal-title'),
    addPhotosModalSubtitle: document.getElementById('add-photos-modal-subtitle'),
    addExtraFiles: document.getElementById('add-extra-files'),
    
    // Courses Tab
    coursesGridView: document.getElementById('courses-grid-view'),
    btnOpenCreateCourseModal: document.getElementById('btn-open-create-course-modal'),
    modalCreateCourse: document.getElementById('modal-create-course'),
    formCreateCourse: document.getElementById('form-create-course'),
    newCourseCode: document.getElementById('new-course-code'),
    newCourseName: document.getElementById('new-course-name'),
    newCourseBranch: document.getElementById('new-course-branch'),
    
    // Toasts
    toastContainer: document.getElementById('toast-container')
};

// ======================= TOAST NOTIFICATIONS ======================= //

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type === 'error' ? 'error' : ''}`;
    toast.innerHTML = `<span>${type === 'error' ? '✕' : '✓'}</span><span>${message}</span>`;
    el.toastContainer.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 200);
    }, 3500);
}

// ======================= TAB NAVIGATION ======================= //

const tabMeta = {
    'take-attendance': {
        title: 'Take Attendance',
        subtitle: 'Facial recognition for classroom sessions via Group Photo or Live Camera'
    },
    'sessions': {
        title: 'Class Sessions',
        subtitle: 'Schedule and review historical attendance records'
    },
    'student-portal': {
        title: 'Student Portal',
        subtitle: 'Check subject-wise attendance percentage and session history'
    },
    'registration': {
        title: 'Register Student',
        subtitle: 'Enroll student details and facial biometrics for automatic matching'
    },
    'courses': {
        title: 'Courses & Roster',
        subtitle: 'Manage academic courses, subjects, and student enrollments'
    }
};

function switchTab(tabId) {
    state.currentTab = tabId;
    el.navItems.forEach(item => {
        item.classList.toggle('active', item.dataset.tab === tabId);
    });
    if (el.bottomNavItems) {
        el.bottomNavItems.forEach(item => {
            item.classList.toggle('active', item.dataset.tab === tabId);
        });
    }
    el.tabPanes.forEach(pane => {
        pane.classList.toggle('active', pane.id === `tab-${tabId}`);
    });

    if (tabMeta[tabId]) {
        el.pageTitle.textContent = tabMeta[tabId].title;
        el.pageSubtitle.textContent = tabMeta[tabId].subtitle;
    }

    // Auto-close mobile drawer and backdrop on selection
    if (el.sidebar && el.sidebar.classList.contains('mobile-open')) {
        el.sidebar.classList.remove('mobile-open');
    }
    if (el.sidebarBackdrop) {
        el.sidebarBackdrop.classList.remove('active');
    }

    // Stop streams if leaving attendance or registration
    if (tabId !== 'take-attendance' && state.webcamStream) {
        stopLiveWebcam();
    }
    if (tabId !== 'registration' && state.regCamStream) {
        stopRegCamera();
    }

    if (tabId === 'sessions') loadSessionsTable();
    if (tabId === 'courses') loadCourses();
    if (tabId === 'registration') loadRegisteredStudentsList();
}

// Mobile sidebar drawer & backdrop toggles
if (el.btnMobileMenu) {
    el.btnMobileMenu.addEventListener('click', () => {
        if (el.sidebar) {
            const isOpen = el.sidebar.classList.toggle('mobile-open');
            if (el.sidebarBackdrop) el.sidebarBackdrop.classList.toggle('active', isOpen);
        }
    });
}
if (el.btnCloseSidebar) {
    el.btnCloseSidebar.addEventListener('click', () => {
        if (el.sidebar) el.sidebar.classList.remove('mobile-open');
        if (el.sidebarBackdrop) el.sidebarBackdrop.classList.remove('active');
    });
}
if (el.sidebarBackdrop) {
    el.sidebarBackdrop.addEventListener('click', () => {
        if (el.sidebar) el.sidebar.classList.remove('mobile-open');
        el.sidebarBackdrop.classList.remove('active');
    });
}

el.navItems.forEach(item => {
    item.addEventListener('click', () => switchTab(item.dataset.tab));
});

if (el.bottomNavItems) {
    el.bottomNavItems.forEach(item => {
        item.addEventListener('click', () => switchTab(item.dataset.tab));
    });
}

function autoDetectSessionDateTime() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    
    if (el.newSessionDate) el.newSessionDate.value = `${year}-${month}-${day}`;
    if (el.newSessionTime) el.newSessionTime.value = `${hours}:${minutes}`;

    if (el.newSessionTitle && (!el.newSessionTitle.value || el.newSessionTitle.value.startsWith('Lecture'))) {
        const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const dateStr = now.toLocaleDateString([], { month: 'short', day: 'numeric' });
        el.newSessionTitle.value = `Lecture // ${dateStr} (${timeStr})`;
    }
}

el.btnQuickNewSession.addEventListener('click', () => {
    autoDetectSessionDateTime();
    openModal('modal-create-session');
});

// ======================= DATA FETCHERS ======================= //

async function loadCourses() {
    try {
        const res = await fetch('/api/courses');
        state.courses = await res.json();
        
        // Populate Course Selectors
        const options = state.courses.map(c => `<option value="${c.id}">${c.code} - ${c.name}</option>`).join('');
        el.newSessionCourse.innerHTML = `<option value="">-- Choose Course --</option>` + options;
        el.filterSessionCourse.innerHTML = `<option value="">All Courses</option>` + options;
        
        // Render Course Cards
        if (el.coursesGridView) {
            el.coursesGridView.innerHTML = state.courses.map(c => `
                <div class="course-admin-card" id="course-card-${c.id}">
                    <div class="course-admin-header">
                        <span class="course-code-tag">${c.code}</span>
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <span class="badge badge-outline">${c.branch}</span>
                            <button type="button" class="btn-course-delete-icon" onclick="deleteCourse(${c.id}, '${c.code.replace(/'/g, "\\'")}', '${c.name.replace(/'/g, "\\'")}')" title="Delete Course ${c.code}">
                                🗑️
                            </button>
                        </div>
                    </div>
                    <h3>${c.name}</h3>
                    <div class="course-admin-branch">${c.branch}</div>
                    <div class="course-admin-stats">
                        <div class="course-admin-stat-item">
                            <span>ENROLLED</span>
                            <span>${c.enrolled_count || 0} Students</span>
                        </div>
                        <div class="course-admin-stat-item">
                            <span>SESSIONS</span>
                            <span>${c.session_count || 0} Classes</span>
                        </div>
                    </div>
                    <div class="course-card-actions">
                        <button class="btn btn-primary btn-sm btn-block" onclick="openCourseRosterModal(${c.id})">
                            👥 Manage Roster & Enroll Students
                        </button>
                        <div class="course-card-btn-row">
                            <a href="/api/export/course/excel?course_id=${c.id}" class="btn btn-outline btn-sm flex-1">
                                📥 Excel Sheet
                            </a>
                            <a href="/api/export/course/csv?course_id=${c.id}" class="btn btn-outline btn-sm">
                                📄 CSV
                            </a>
                            <button type="button" class="btn btn-danger-outline btn-sm" onclick="deleteCourse(${c.id}, '${c.code.replace(/'/g, "\\'")}', '${c.name.replace(/'/g, "\\'")}')" title="Delete Course ${c.code}">
                                🗑️ Delete
                            </button>
                        </div>
                    </div>
                </div>
            `).join('');
        }
    } catch (err) {
        console.error('Error loading courses:', err);
    }
}

async function loadSessions(selectSessionId = null) {
    try {
        const res = await fetch('/api/sessions');
        state.sessions = await res.json();

        el.sessionSelect.innerHTML = `<option value="">-- Choose a Class Session --</option>` +
            state.sessions.map(s => `
                <option value="${s.id}">[${s.session_date}${s.session_time ? ' ' + s.session_time : ''}] ${s.course_code} - ${s.title}</option>
            `).join('');

        if (selectSessionId) {
            el.sessionSelect.value = selectSessionId;
            onSessionSelected(selectSessionId);
        } else if (state.sessions.length > 0 && !el.sessionSelect.value) {
            el.sessionSelect.value = state.sessions[0].id;
            onSessionSelected(state.sessions[0].id);
        }
    } catch (err) {
        console.error('Error loading sessions:', err);
    }
}

async function loadStudents() {
    try {
        const res = await fetch('/api/students');
        state.students = await res.json();

        el.studentPortalSelect.innerHTML = `<option value="">-- Quick Select --</option>` +
            state.students.map(s => `<option value="${s.roll_no}">${s.roll_no} - ${s.name}</option>`).join('');

        loadRegisteredStudentsList();
    } catch (err) {
        console.error('Error loading students:', err);
    }
}

function loadRegisteredStudentsList() {
    if (!el.registeredStudentsList) return;
    el.totalRegisteredBadge.textContent = `${state.students.length} Students`;
    
    if (state.students.length === 0) {
        el.registeredStudentsList.innerHTML = `<p class="text-muted text-center py-4">No students enrolled yet.</p>`;
        return;
    }

    el.registeredStudentsList.innerHTML = state.students.map(s => `
        <div class="student-list-item">
            <div class="student-item-left">
                <img src="${s.photo_path ? '/' + s.photo_path : '/static/avatar-placeholder.png'}" 
                     class="student-thumb" 
                     onerror="this.src='data:image/svg+xml;utf8,<svg xmlns=\'http://www.w3.org/2000/svg\' width=\'36\' height=\'36\' viewBox=\'0 0 24 24\' fill=\'none\' stroke=\'white\' stroke-width=\'2\'><circle cx=\'12\' cy=\'8\' r=\'4\'/><path d=\'M6 20v-2a6 6 0 0 1 12 0v2\'/></svg>'">
                <div class="student-item-info">
                    <h4>${s.name}</h4>
                    <span>${s.roll_no} • ${s.branch}</span>
                </div>
            </div>
            <div style="display: flex; align-items: center; gap: 6px;">
                <span class="badge badge-outline">${s.embedding_count || 1} Photo(s)</span>
                <button type="button" class="btn-add-photos" onclick="openAddPhotosModal(${s.id}, '${s.name.replace(/'/g, "\\'")}', '${s.roll_no}')">+ Add Photos</button>
            </div>
        </div>
    `).join('');
}

// ======================= ATTENDANCE WORKSPACE ======================= //

el.sessionSelect.addEventListener('change', (e) => {
    onSessionSelected(e.target.value);
});

async function onSessionSelected(sessionId) {
    if (!sessionId) {
        state.selectedSessionId = null;
        updateSessionStats(null);
        renderRoster([]);
        updateExportLinks(null);
        return;
    }

    state.selectedSessionId = parseInt(sessionId);

    try {
        const res = await fetch(`/api/sessions/${state.selectedSessionId}/attendance`);
        const data = await res.json();
        updateSessionStats(data.session, data.records);
        renderRoster(data.records);
        updateExportLinks(state.selectedSessionId, data.session ? data.session.course_id : null);
    } catch (err) {
        console.error('Failed to load session attendance:', err);
        showToast('Error loading session attendance', 'error');
    }
}

function updateSessionStats(session, records = []) {
    if (!session) {
        el.statCourseCode.textContent = '--';
        el.statEnrolled.textContent = '0';
        el.statPresent.textContent = '0';
        el.statRate.textContent = '0%';
        return;
    }

    const total = records.length;
    const present = records.filter(r => r.status === 'Present').length;
    const rate = total > 0 ? Math.round((present / total) * 100) : 0;

    el.statCourseCode.textContent = session.course_code;
    el.statEnrolled.textContent = total;
    el.statPresent.textContent = present;
    el.statRate.textContent = `${rate}%`;
}

function updateExportLinks(sessionId, courseId = null) {
    if (!sessionId) {
        el.btnExportExcel.href = '#';
        el.btnExportCsv.href = '#';
        if (el.btnExportCourseExcel) el.btnExportCourseExcel.href = '#';
        [el.btnExportExcel, el.btnExportCsv, el.btnExportCourseExcel].forEach(btn => {
            if (btn) {
                btn.style.pointerEvents = 'none';
                btn.style.opacity = '0.5';
            }
        });
    } else {
        el.btnExportExcel.href = `/api/export/excel?session_id=${sessionId}`;
        el.btnExportCsv.href = `/api/export/csv?session_id=${sessionId}`;
        if (el.btnExportCourseExcel && courseId) {
            el.btnExportCourseExcel.href = `/api/export/course/excel?course_id=${courseId}`;
            el.btnExportCourseExcel.style.pointerEvents = 'auto';
            el.btnExportCourseExcel.style.opacity = '1';
        }
        el.btnExportExcel.style.pointerEvents = 'auto';
        el.btnExportCsv.style.pointerEvents = 'auto';
        el.btnExportExcel.style.opacity = '1';
        el.btnExportCsv.style.opacity = '1';
    }
}

function renderRoster(records) {
    if (!records) records = [];

    // Always sort records so that ABSENT students appear at the top!
    const sortedRecords = [...records].sort((a, b) => {
        const aStatus = a.status || 'Absent';
        const bStatus = b.status || 'Absent';
        if (aStatus === 'Absent' && bStatus === 'Present') return -1;
        if (aStatus === 'Present' && bStatus === 'Absent') return 1;
        return (a.roll_no || '').localeCompare(b.roll_no || '');
    });

    const absentCount = sortedRecords.filter(r => (r.status || 'Absent') === 'Absent').length;
    const presentCount = sortedRecords.filter(r => r.status === 'Present').length;

    el.rosterCountLabel.textContent = `${sortedRecords.length} enrolled`;
    if (el.rosterAbsentBadge) el.rosterAbsentBadge.textContent = `${absentCount} Absent (at top)`;
    if (el.rosterPresentBadge) el.rosterPresentBadge.textContent = `${presentCount} Present`;

    if (sortedRecords.length === 0) {
        el.rosterTbody.innerHTML = `
            <tr><td colspan="6" class="text-center text-muted">No students enrolled in this course session</td></tr>
        `;
        return;
    }

    el.rosterTbody.innerHTML = sortedRecords.map(r => {
        const isPresent = r.status === 'Present';
        const confText = r.confidence > 0 ? `${Math.round(r.confidence * 100)}%` : '-';
        const methodText = r.marked_method || 'Initial';
        const photoUrl = r.photo_path ? '/' + r.photo_path : '';
        const metaLine = `${r.roll_no}${r.confidence > 0 ? ' • ' + confText + ' AI' : (r.marked_method ? ' • ' + r.marked_method : '')}`;

        return `
            <tr class="roster-row ${isPresent ? 'row-present' : 'row-absent'}">
                <td class="col-roll"><strong>${r.roll_no}</strong></td>
                <td class="col-student">
                    <div class="student-col">
                        <img src="${photoUrl}" class="avatar-mini" alt="${r.name}" onerror="this.src='data:image/svg+xml;utf8,<svg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'28\\' height=\\'28\\' viewBox=\\'0 0 24 24\\' fill=\\'none\\' stroke=\\'%23888\\' stroke-width=\\'2\\'><circle cx=\\'12\\' cy=\\'8\\' r=\\'4\\'/><path d=\\'M6 20v-2a6 6 0 0 1 12 0v2\\'/></svg>'">
                        <div class="student-info-cell">
                            <span class="student-name">${r.name}</span>
                            <span class="student-meta-mobile">${metaLine}</span>
                        </div>
                    </div>
                </td>
                <td class="col-status">
                    <span class="badge ${isPresent ? 'badge-present' : 'badge-absent'}">
                        ${r.status}
                    </span>
                </td>
                <td class="col-conf">${confText}</td>
                <td class="col-method"><span class="text-muted">${methodText}</span></td>
                <td class="col-action">
                    <button type="button" class="toggle-btn ${isPresent ? 'btn-mark-absent' : 'btn-mark-present'}" onclick="toggleStudentStatus(${r.student_id}, '${isPresent ? 'Absent' : 'Present'}')">
                        ${isPresent ? '✕ Mark Absent' : '✓ Mark Present'}
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

window.toggleStudentStatus = async function(studentId, newStatus) {
    if (!state.selectedSessionId) return;
    try {
        const res = await fetch(`/api/sessions/${state.selectedSessionId}/attendance/toggle`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ student_id: studentId, status: newStatus })
        });
        if (res.ok) {
            onSessionSelected(state.selectedSessionId);
            showToast(`Attendance updated: ${newStatus}`);
        }
    } catch (err) {
        console.error('Toggle error:', err);
    }
};

// ======================= MODE SWITCHING ======================= //

el.modeBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        const mode = btn.dataset.mode;
        el.modeBtns.forEach(b => b.classList.toggle('active', b.dataset.mode === mode));
        if (mode === 'group-photo') {
            el.panelGroupPhoto.classList.add('active');
            el.panelLiveWebcam.classList.remove('active');
            stopLiveWebcam();
        } else {
            el.panelGroupPhoto.classList.remove('active');
            el.panelLiveWebcam.classList.add('active');
        }
    });
});

// ======================= GROUP PHOTO ATTENDANCE ======================= //

el.groupDropzone.addEventListener('click', (e) => {
    // Only open file picker if clicking prompt area, not buttons
    if (e.target.closest('#btn-clear-group-img') || 
        e.target.closest('#btn-toggle-group-annotation') || 
        e.target.closest('#btn-add-more-group-photo') ||
        e.target.closest('.staged-thumb-item')) {
        return;
    }
    if (state.stagedGroupPhotos.length === 0) {
        el.groupFileInput.click();
    }
});

// Mobile Quick Camera & Gallery Buttons
if (el.btnMobileSnapPhoto && el.groupCameraInput) {
    el.btnMobileSnapPhoto.addEventListener('click', () => {
        el.groupCameraInput.click();
    });
    el.groupCameraInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files.length > 0) {
            handleAddGroupFiles(e.target.files);
            el.groupCameraInput.value = '';
        }
    });
}

if (el.btnAddMoreGroupPhoto && el.groupCameraInput) {
    el.btnAddMoreGroupPhoto.addEventListener('click', (e) => {
        e.stopPropagation();
        // On mobile: open camera directly. On desktop: open file gallery picker.
        if (isMobile) {
            el.groupCameraInput.click();
        } else {
            el.groupFileInput.click();
        }
    });
}

if (el.btnMobileGalleryPhoto && el.groupFileInput) {
    el.btnMobileGalleryPhoto.addEventListener('click', () => {
        el.groupFileInput.click();
    });
}

el.groupFileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files.length > 0) {
        handleAddGroupFiles(e.target.files);
        el.groupFileInput.value = '';
    }
});

['dragenter', 'dragover'].forEach(name => {
    el.groupDropzone.addEventListener(name, (e) => {
        e.preventDefault();
        el.groupDropzone.style.borderColor = '#ffffff';
    });
});

['dragleave', 'drop'].forEach(name => {
    el.groupDropzone.addEventListener(name, (e) => {
        e.preventDefault();
        el.groupDropzone.style.borderColor = 'var(--border-strong)';
    });
});

el.groupDropzone.addEventListener('drop', (e) => {
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        handleAddGroupFiles(e.dataTransfer.files);
    }
});

function optimizeImageForUpload(file, maxDim = 1600) {
    return new Promise((resolve) => {
        if (!file || !file.type.startsWith('image/')) {
            return resolve(file);
        }
        if (file.size < 400 * 1024) {
            return resolve(file);
        }
        const img = new Image();
        const url = URL.createObjectURL(file);
        img.onload = () => {
            URL.revokeObjectURL(url);
            let w = img.width;
            let h = img.height;
            if (w <= maxDim && h <= maxDim) {
                return resolve(file);
            }
            if (w > h) {
                h = Math.round((h * maxDim) / w);
                w = maxDim;
            } else {
                w = Math.round((w * maxDim) / h);
                h = maxDim;
            }
            const canvas = document.createElement('canvas');
            canvas.width = w;
            canvas.height = h;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(img, 0, 0, w, h);
            canvas.toBlob((blob) => {
                if (blob) {
                    const cleanName = file.name ? file.name.replace(/\.[^/.]+$/, ".jpg") : "photo.jpg";
                    const newFile = new File([blob], cleanName, { type: 'image/jpeg' });
                    resolve(newFile);
                } else {
                    resolve(file);
                }
            }, 'image/jpeg', 0.90);
        };
        img.onerror = () => {
            URL.revokeObjectURL(url);
            resolve(file);
        };
        img.src = url;
    });
}

async function handleAddGroupFiles(fileList) {
    if (!fileList || fileList.length === 0) return;
    const files = Array.from(fileList);
    showToast(`Adding ${files.length} photo(s)...`);

    for (const file of files) {
        try {
            const optimizedFile = await optimizeImageForUpload(file, 1600);
            const dataUrl = await new Promise((resolve) => {
                const reader = new FileReader();
                reader.onload = (ev) => resolve(ev.target.result);
                reader.readAsDataURL(optimizedFile);
            });
            state.stagedGroupPhotos.push({
                file: optimizedFile,
                originalSrc: dataUrl,
                annotatedSrc: null
            });
        } catch (e) {
            console.error('Error adding photo:', e);
        }
    }

    if (state.stagedGroupPhotos.length > 0) {
        state.activeGroupPhotoIndex = state.stagedGroupPhotos.length - 1;
        state.showingAnnotatedGroup = false;
        renderStagedGroupPhotos();
        if (window.innerWidth <= 768 && el.groupPreviewWrapper) {
            el.groupPreviewWrapper.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }
}

function renderStagedGroupPhotos() {
    const list = state.stagedGroupPhotos;
    if (list.length === 0) {
        el.groupPreviewWrapper.style.display = 'none';
        el.dropzonePrompt.style.display = 'block';
        if (el.stagedThumbnailsRow) el.stagedThumbnailsRow.style.display = 'none';
        if (el.btnProcessGroupText) el.btnProcessGroupText.textContent = '⚡ Scan & Identify Faces';
        state.selectedGroupFile = null;
        state.originalGroupPhotoSrc = null;
        state.annotatedGroupPhotoSrc = null;
        return;
    }

    el.dropzonePrompt.style.display = 'none';
    el.groupPreviewWrapper.style.display = 'flex';

    if (state.activeGroupPhotoIndex >= list.length) {
        state.activeGroupPhotoIndex = list.length - 1;
    }

    const activeItem = list[state.activeGroupPhotoIndex];
    state.selectedGroupFile = activeItem.file;
    state.originalGroupPhotoSrc = activeItem.originalSrc;
    state.annotatedGroupPhotoSrc = activeItem.annotatedSrc;

    // Display annotated or original
    if (state.showingAnnotatedGroup && activeItem.annotatedSrc) {
        el.groupPreviewImg.src = activeItem.annotatedSrc;
        if (el.btnToggleGroupAnnotation) {
            el.btnToggleGroupAnnotation.style.display = 'inline-block';
            el.btnToggleGroupAnnotation.textContent = '👁️ Hide Boxes';
        }
    } else {
        el.groupPreviewImg.src = activeItem.originalSrc;
        if (el.btnToggleGroupAnnotation) {
            el.btnToggleGroupAnnotation.style.display = activeItem.annotatedSrc ? 'inline-block' : 'none';
            el.btnToggleGroupAnnotation.textContent = '👁️ Show Boxes';
        }
    }

    if (el.stagedPhotosCount) {
        el.stagedPhotosCount.textContent = `${list.length} Classroom Photo${list.length > 1 ? 's' : ''} Staged (Angle ${state.activeGroupPhotoIndex + 1} of ${list.length})`;
    }

    if (el.btnProcessGroupText) {
        el.btnProcessGroupText.textContent = `⚡ Scan & Identify Faces in ${list.length} Photo${list.length > 1 ? 's' : ''}`;
    }

    // Thumbnails row for switching between angles
    if (el.stagedThumbnailsRow) {
        el.stagedThumbnailsRow.style.display = 'flex';
        el.stagedThumbnailsRow.innerHTML = list.map((item, idx) => `
            <div class="staged-thumb-item ${idx === state.activeGroupPhotoIndex ? 'active' : ''}" onclick="switchActiveGroupPhoto(${idx})" title="View Angle ${idx + 1}">
                <img src="${item.annotatedSrc || item.originalSrc}" alt="Angle ${idx + 1}">
                <button type="button" class="staged-thumb-del" onclick="removeStagedGroupPhoto(event, ${idx})" title="Remove photo">✕</button>
            </div>
        `).join('');
    }
}

window.switchActiveGroupPhoto = function(idx) {
    state.activeGroupPhotoIndex = idx;
    renderStagedGroupPhotos();
};

window.removeStagedGroupPhoto = function(event, idx) {
    if (event) event.stopPropagation();
    state.stagedGroupPhotos.splice(idx, 1);
    if (state.activeGroupPhotoIndex >= state.stagedGroupPhotos.length) {
        state.activeGroupPhotoIndex = Math.max(0, state.stagedGroupPhotos.length - 1);
    }
    renderStagedGroupPhotos();
};

el.btnClearGroupImg.addEventListener('click', (e) => {
    e.stopPropagation();
    state.stagedGroupPhotos = [];
    state.activeGroupPhotoIndex = 0;
    state.selectedGroupFile = null;
    state.originalGroupPhotoSrc = null;
    state.annotatedGroupPhotoSrc = null;
    el.groupFileInput.value = '';
    el.groupPreviewImg.src = '';
    if (el.btnToggleGroupAnnotation) {
        el.btnToggleGroupAnnotation.style.display = 'none';
    }
    el.dropzonePrompt.style.display = 'block';
    el.groupPreviewWrapper.style.display = 'none';
    if (el.stagedThumbnailsRow) el.stagedThumbnailsRow.style.display = 'none';
    el.aiScanSummary.style.display = 'none';
    if (el.btnProcessGroupText) el.btnProcessGroupText.textContent = '⚡ Scan & Identify Faces';
});

if (el.btnToggleGroupAnnotation) {
    el.btnToggleGroupAnnotation.addEventListener('click', (e) => {
        e.stopPropagation();
        if (!state.annotatedGroupPhotoSrc || !state.originalGroupPhotoSrc) return;
        state.showingAnnotatedGroup = !state.showingAnnotatedGroup;
        renderStagedGroupPhotos();
    });
}

el.btnProcessGroup.addEventListener('click', async () => {
    if (!state.selectedSessionId) {
        showToast('Please select an active Class Session first!', 'error');
        return;
    }
    if (!state.stagedGroupPhotos || state.stagedGroupPhotos.length === 0) {
        showToast('Please upload or snap at least one classroom photo first!', 'error');
        return;
    }

    el.btnProcessGroup.disabled = true;
    el.btnProcessGroup.innerHTML = `<span>Scanning Faces with ArcFace across ${state.stagedGroupPhotos.length} photo(s)...</span>`;

    // Show fullscreen loading overlay (critical for mobile to prevent double-taps)
    showScanOverlay(`SCANNING ${state.stagedGroupPhotos.length} PHOTO(S) WITH ARCFACE...`);

    const formData = new FormData();
    formData.append('session_id', state.selectedSessionId);
    formData.append('threshold', state.threshold || 0.38);
    for (const item of state.stagedGroupPhotos) {
        formData.append('images', item.file);
    }

    try {
        const res = await fetch('/api/attendance/recognize-group', {
            method: 'POST',
            body: formData
        });

        if (!res.ok) {
            const errData = await res.json();
            throw new Error(errData.detail || 'Scan failed');
        }

        const data = await res.json();

        // Update all staged items with their respective annotated predictions
        if (data.annotated_images && data.annotated_images.length > 0) {
            data.annotated_images.forEach((imgB64, i) => {
                if (state.stagedGroupPhotos[i]) {
                    state.stagedGroupPhotos[i].annotatedSrc = imgB64;
                }
            });
            state.showingAnnotatedGroup = true;
            renderStagedGroupPhotos();
        } else if (data.annotated_image && state.stagedGroupPhotos[0]) {
            state.stagedGroupPhotos[0].annotatedSrc = data.annotated_image;
            state.showingAnnotatedGroup = true;
            renderStagedGroupPhotos();
        }

        // Display results summary
        el.aiScanSummary.style.display = 'block';
        el.scanFacesCount.textContent = `${data.total_faces_detected} faces across ${data.total_images_processed || state.stagedGroupPhotos.length} photo(s)`;

        if (data.recognized_names.length > 0) {
            el.scanRecognizedNames.innerHTML = `<strong>Identified (${data.recognized_names.length}):</strong> ${data.recognized_names.join(', ')}`;
            showToast(`Marked ${data.recognized_names.length} student(s) Present across all angles!`);
        } else {
            el.scanRecognizedNames.textContent = 'No enrolled faces matched confidence threshold.';
            showToast('No enrolled students matched', 'error');
        }

        // Refresh Roster Table (Absent students will be sorted to the very top!)
        onSessionSelected(state.selectedSessionId);

    } catch (err) {
        console.error(err);
        showToast(err.message, 'error');
    } finally {
        hideScanOverlay();
        el.btnProcessGroup.disabled = false;
        if (el.btnProcessGroupText) {
            el.btnProcessGroupText.textContent = `⚡ Scan & Identify Faces in ${state.stagedGroupPhotos.length} Photo${state.stagedGroupPhotos.length > 1 ? 's' : ''}`;
        } else {
            el.btnProcessGroup.innerHTML = `<span>Scan & Identify Faces</span>`;
        }
    }
});

// ======================= LIVE WEBCAM ATTENDANCE ======================= //

el.btnStartWebcam.addEventListener('click', async () => {
    if (!state.selectedSessionId) {
        showToast('Please select a Class Session first!', 'error');
        return;
    }
    startLiveWebcam();
});

el.btnStopWebcam.addEventListener('click', () => {
    stopLiveWebcam();
});

// ======================= REFINED MINIMALIST HUD & WEBCAM CONTROLS ======================= //

function setBoxStyle(style) {
    state.boxStyle = style;
    if (el.stylePills) {
        el.stylePills.forEach(p => {
            p.classList.toggle('active', p.dataset.style === style);
        });
    }
    if (el.btnToggleBoxes) {
        if (style === 'none') {
            el.btnToggleBoxes.textContent = '👁️ Show Boxes';
            el.btnToggleBoxes.classList.add('btn-primary');
            el.btnToggleBoxes.classList.remove('btn-outline');
        } else {
            el.btnToggleBoxes.textContent = '👁️ Hide Boxes';
            el.btnToggleBoxes.classList.remove('btn-primary');
            el.btnToggleBoxes.classList.add('btn-outline');
        }
    }
}

// Quick toggle Hide / Show recognition boxes
if (el.btnToggleBoxes) {
    el.btnToggleBoxes.addEventListener('click', () => {
        if (state.boxStyle === 'none') {
            setBoxStyle('minimal');
            showToast('Face recognition boxes enabled');
        } else {
            setBoxStyle('none');
            showToast('Face recognition boxes hidden (clean view)');
        }
    });
}

// Box Style Pills ('minimal' | 'corners' | 'none')
if (el.stylePills) {
    el.stylePills.forEach(pill => {
        pill.addEventListener('click', () => {
            const style = pill.dataset.style;
            setBoxStyle(style);
            showToast(`Box style: ${style === 'none' ? 'Hidden (Clean)' : style}`);
        });
    });
}

// Name tag toggle
if (el.toggleHudLabels) {
    el.toggleHudLabels.addEventListener('change', (e) => {
        state.showNameTags = e.target.checked;
        showToast(e.target.checked ? 'Name tags enabled' : 'Name tags hidden');
    });
}

// Laser line toggle
if (el.toggleHudLaser) {
    el.toggleHudLaser.addEventListener('change', (e) => {
        state.showLaser = e.target.checked;
        if (el.hudLaserLine) {
            el.hudLaserLine.classList.toggle('paused', !e.target.checked);
        }
    });
}

// Auto-mark toggle
if (el.toggleHudAutoMark) {
    el.toggleHudAutoMark.addEventListener('change', (e) => {
        state.autoMark = e.target.checked;
        showToast(e.target.checked ? 'Auto-Marking Active' : 'Auto-Marking Paused (Preview Only)');
    });
}

// Speed Pills
if (el.speedPills) {
    el.speedPills.forEach(pill => {
        pill.addEventListener('click', () => {
            el.speedPills.forEach(p => p.classList.remove('active'));
            pill.classList.add('active');
            state.webcamScanInterval = parseInt(pill.dataset.interval) || 1400;
            if (state.webcamStream) {
                if (state.webcamInterval) clearInterval(state.webcamInterval);
                state.webcamInterval = setInterval(processWebcamFrame, state.webcamScanInterval);
            }
            showToast(`Scan rate set to ${(state.webcamScanInterval / 1000).toFixed(1)}s`);
        });
    });
}

// Match Sensitivity (Threshold) Slider
if (el.inputHudThreshold) {
    el.inputHudThreshold.addEventListener('input', (e) => {
        const val = parseFloat(e.target.value);
        state.threshold = val;
        if (el.labelHudThreshold) el.labelHudThreshold.textContent = val.toFixed(2);
    });
}

if (el.btnFlipWebcam) {
    el.btnFlipWebcam.addEventListener('click', async () => {
        state.webcamFacingMode = state.webcamFacingMode === 'environment' ? 'user' : 'environment';
        showToast(`Switching camera: ${state.webcamFacingMode === 'environment' ? 'Rear (Classroom)' : 'Front (Selfie)'}`);
        if (state.webcamStream) {
            stopLiveWebcam();
            startLiveWebcam();
        }
    });
}

// ResizeObserver: keep HUD canvas synced when phone rotates or window resizes
if (el.webcamHudCanvas && typeof ResizeObserver !== 'undefined') {
    const hudResizeObserver = new ResizeObserver(() => {
        if (el.webcamHudCanvas) {
            el.webcamHudCanvas.width = el.webcamHudCanvas.clientWidth;
            el.webcamHudCanvas.height = el.webcamHudCanvas.clientHeight;
        }
    });
    const webcamWrapper = el.webcamHudCanvas.closest('.webcam-viewport') || el.webcamHudCanvas.parentElement;
    if (webcamWrapper) hudResizeObserver.observe(webcamWrapper);
}

async function startLiveWebcam() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        showToast('Live video streaming requires HTTPS or localhost on Android Chrome. Please switch to "Group Photo AI Upload" to click photos directly with phone camera!', 'error');
        // Auto-switch to group photo mode on mobile
        const groupModeBtn = document.querySelector('[data-mode="group-photo"]');
        if (groupModeBtn) {
            groupModeBtn.click();
        }
        return;
    }

    try {
        const constraints = {
            video: {
                width: { ideal: 1280, max: 1920 },
                height: { ideal: 720, max: 1080 },
                facingMode: state.webcamFacingMode
            }
        };
        state.webcamStream = await navigator.mediaDevices.getUserMedia(constraints);
        el.webcamVideo.srcObject = state.webcamStream;
        // Mirror video for front (selfie) camera — looks natural to user; canvas capture is NOT mirrored
        el.webcamVideo.classList.toggle('webcam-mirrored', state.webcamFacingMode === 'user');
        el.btnStartWebcam.disabled = true;
        el.btnStopWebcam.disabled = false;
        el.btnSnapFrame.disabled = false;
        el.webcamHudStatus.textContent = `OPTICAL TRACKING // ${state.webcamFacingMode.toUpperCase()}`;

        // Start 60 FPS Cyber HUD Animation Loop
        state.liveDetectedTargets = [];
        if (!state.hudAnimationId) {
            state.hudAnimationId = requestAnimationFrame(renderHudLoop);
        }

        // Start auto-processing frames
        state.webcamInterval = setInterval(processWebcamFrame, state.webcamScanInterval);
        showToast(`Biometric HUD online (${state.webcamFacingMode === 'environment' ? 'Rear' : 'Front'})`);
    } catch (err) {
        console.error('Webcam error:', err);
        showToast('Camera access denied or unavailable: ' + err.message, 'error');
    }
}

function stopLiveWebcam() {
    if (state.webcamInterval) {
        clearInterval(state.webcamInterval);
        state.webcamInterval = null;
    }
    if (state.hudAnimationId) {
        cancelAnimationFrame(state.hudAnimationId);
        state.hudAnimationId = null;
    }
    if (state.webcamStream) {
        state.webcamStream.getTracks().forEach(t => t.stop());
        state.webcamStream = null;
    }
    if (el.webcamHudCanvas) {
        const ctx = el.webcamHudCanvas.getContext('2d');
        ctx.clearRect(0, 0, el.webcamHudCanvas.width, el.webcamHudCanvas.height);
    }
    el.webcamVideo.srcObject = null;
    el.webcamVideo.classList.remove('webcam-mirrored');
    el.btnStartWebcam.disabled = false;
    el.btnStopWebcam.disabled = true;
    el.btnSnapFrame.disabled = true;
    el.webcamHudStatus.textContent = 'CAMERA OFFLINE';
    el.tickerTags.innerHTML = `<span class="muted-tag">No targets detected in optical frame</span>`;
}

// Smooth rounded rect helper
function drawRoundedRect(ctx, x, y, w, h, r) {
    if (ctx.roundRect) {
        ctx.beginPath();
        ctx.roundRect(x, y, w, h, r);
        return;
    }
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r);
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
}

// 60FPS Clean Face Recognition Overlay Renderer
function renderHudLoop() {
    if (!state.webcamStream) {
        if (state.hudAnimationId) {
            cancelAnimationFrame(state.hudAnimationId);
            state.hudAnimationId = null;
        }
        return;
    }

    const canvas = el.webcamHudCanvas;
    if (!canvas) return;

    if (canvas.width !== canvas.clientWidth || canvas.height !== canvas.clientHeight) {
        canvas.width = canvas.clientWidth;
        canvas.height = canvas.clientHeight;
    }

    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // If user chose to hide boxes, keep canvas 100% clean
    if (state.boxStyle === 'none') {
        state.hudAnimationId = requestAnimationFrame(renderHudLoop);
        return;
    }

    const now = Date.now();
    // Keep targets alive for 2.2s after last detection
    state.liveDetectedTargets = state.liveDetectedTargets.filter(t => (now - t.lastSeen) < 2200);

    state.liveDetectedTargets.forEach(t => {
        // Fluid interpolation
        t.x += (t.targetX - t.x) * 0.35;
        t.y += (t.targetY - t.y) * 0.35;
        t.w += (t.targetW - t.w) * 0.35;
        t.h += (t.targetH - t.h) * 0.35;

        const x = t.x;
        const y = t.y;
        const w = t.w;
        const h = t.h;

        const isMatched = t.is_matched;
        const strokeColor = isMatched ? '#22c55e' : '#f59e0b';
        const glowColor = isMatched ? 'rgba(34, 197, 94, 0.4)' : 'rgba(245, 158, 11, 0.3)';

        // 1. Box Rendering (Minimal Pill or Corner Brackets)
        ctx.save();
        ctx.strokeStyle = strokeColor;
        ctx.lineWidth = 1.8;
        ctx.shadowColor = glowColor;
        ctx.shadowBlur = 6;

        if (state.boxStyle === 'minimal') {
            // Sleek thin rounded rectangle
            drawRoundedRect(ctx, x, y, w, h, 8);
            ctx.stroke();
        } else if (state.boxStyle === 'corners') {
            // Elegant micro corner brackets
            const bLen = Math.max(12, Math.min(22, w * 0.22));
            const r = 4;

            // Top-Left
            ctx.beginPath();
            ctx.moveTo(x, y + bLen);
            ctx.lineTo(x, y + r);
            ctx.arcTo(x, y, x + r, y, r);
            ctx.lineTo(x + bLen, y);
            ctx.stroke();

            // Top-Right
            ctx.beginPath();
            ctx.moveTo(x + w - bLen, y);
            ctx.lineTo(x + w, y);
            ctx.arcTo(x + w, y, x + w, y + r, r);
            ctx.lineTo(x + w, y + bLen);
            ctx.stroke();

            // Bottom-Left
            ctx.beginPath();
            ctx.moveTo(x, y + h - bLen);
            ctx.lineTo(x, y + h - r);
            ctx.arcTo(x, y + h, x + r, y + h, r);
            ctx.lineTo(x + bLen, y + h);
            ctx.stroke();

            // Bottom-Right
            ctx.beginPath();
            ctx.moveTo(x + w - bLen, y + h);
            ctx.lineTo(x + w, y + h);
            ctx.arcTo(x + w, y + h, x + w, y + h - r, r);
            ctx.lineTo(x + w, y + h - bLen);
            ctx.stroke();
        }
        ctx.restore();

        // 2. Minimalist Floating Pill Name Tag
        if (state.showNameTags) {
            ctx.save();
            ctx.font = '500 11px system-ui, -apple-system, sans-serif';
            
            const pct = Math.round((t.score || 0) * 100);
            const labelText = isMatched 
                ? `${t.name} (${pct}%)`
                : `Scanning... (${pct}%)`;

            const textMetrics = ctx.measureText(labelText);
            const pillW = textMetrics.width + 24;
            const pillH = 22;
            const pillX = Math.max(4, Math.min(canvas.width - pillW - 4, x + (w - pillW) / 2));
            const pillY = Math.max(4, y - pillH - 6);

            // Frosted dark pill background
            ctx.fillStyle = 'rgba(10, 14, 18, 0.88)';
            ctx.strokeStyle = isMatched ? 'rgba(34, 197, 94, 0.6)' : 'rgba(255, 255, 255, 0.15)';
            ctx.lineWidth = 1;

            drawRoundedRect(ctx, pillX, pillY, pillW, pillH, 11);
            ctx.fill();
            ctx.stroke();

            // Indicator dot
            ctx.beginPath();
            ctx.fillStyle = strokeColor;
            ctx.arc(pillX + 10, pillY + pillH / 2, 3.5, 0, Math.PI * 2);
            ctx.fill();

            // Text
            ctx.fillStyle = isMatched ? '#ffffff' : '#cbd5e1';
            ctx.textBaseline = 'middle';
            ctx.fillText(labelText, pillX + 18, pillY + pillH / 2 + 0.5);

            ctx.restore();
        }
    });

    state.hudAnimationId = requestAnimationFrame(renderHudLoop);
}

el.btnSnapFrame.addEventListener('click', () => {
    processWebcamFrame(true);
});

async function processWebcamFrame(isManualSnap = false) {
    if (!state.selectedSessionId || !state.webcamStream) return;

    const video = el.webcamVideo;
    if (video.videoWidth === 0 || video.videoHeight === 0) return;

    const canvas = el.webcamCanvas;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const frameB64 = canvas.toDataURL('image/jpeg', 0.85);

    try {
        const res = await fetch('/api/attendance/recognize-frame', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: state.selectedSessionId,
                frame_b64: frameB64,
                threshold: state.threshold || 0.38
            })
        });

        if (!res.ok) return;

        const data = await res.json();
        
        // Map backend detections into live tracked targets for 60FPS overlay
        if (data.detections && el.webcamHudCanvas) {
            const frameW = canvas.width;
            const frameH = canvas.height;
            const displayW = el.webcamHudCanvas.clientWidth;
            const displayH = el.webcamHudCanvas.clientHeight;
            const scaleX = displayW / frameW;
            const scaleY = displayH / frameH;

            data.detections.forEach(det => {
                const [bx, by, bw, bh] = det.bbox;
                const targetX = bx * scaleX;
                const targetY = by * scaleY;
                const targetW = bw * scaleX;
                const targetH = bh * scaleY;

                const existing = state.liveDetectedTargets.find(t => 
                    (det.student_id && t.student_id === det.student_id) ||
                    Math.hypot(t.x - targetX, t.y - targetY) < 70
                );

                if (existing) {
                    existing.targetX = targetX;
                    existing.targetY = targetY;
                    existing.targetW = targetW;
                    existing.targetH = targetH;
                    existing.score = det.score;
                    existing.is_matched = det.is_matched;
                    existing.name = det.name;
                    existing.roll_no = det.roll_no;
                    existing.lastSeen = Date.now();
                } else {
                    state.liveDetectedTargets.push({
                        x: targetX,
                        y: targetY,
                        w: targetW,
                        h: targetH,
                        targetX,
                        targetY,
                        targetW,
                        targetH,
                        score: det.score,
                        is_matched: det.is_matched,
                        student_id: det.student_id,
                        name: det.name,
                        roll_no: det.roll_no,
                        lastSeen: Date.now()
                    });
                }
            });
        }

        if (data.marked_students && data.marked_students.length > 0) {
            el.tickerTags.innerHTML = data.marked_students.map(name => `
                <span class="ticker-tag" style="background: #0d2818; color: #4ade80; border: 1px solid #22c55e;">
                    ✓ ${name}
                </span>
            `).join('');
            if (isManualSnap) {
                showToast(`Verified: ${data.marked_students.join(', ')}`);
            }
            if (state.autoMark) {
                onSessionSelected(state.selectedSessionId);
            }
        } else {
            if (isManualSnap) {
                showToast('No matching face recognized in frame', 'error');
            }
        }
    } catch (err) {
        console.error('Frame processing error:', err);
    }
}

// ======================= SESSIONS TAB ======================= //

async function loadSessionsTable() {
    try {
        const courseFilter = el.filterSessionCourse.value;
        const url = courseFilter ? `/api/sessions?course_id=${courseFilter}` : `/api/sessions`;
        const res = await fetch(url);
        const sessions = await res.json();

        if (sessions.length === 0) {
            el.sessionsTableBody.innerHTML = `
                <tr><td colspan="6" class="text-center text-muted">No class sessions scheduled yet. Click "+ Create New Session" to start.</td></tr>
            `;
            return;
        }

        el.sessionsTableBody.innerHTML = sessions.map(s => {
            const pct = s.total_count > 0 ? Math.round((s.present_count / s.total_count) * 100) : 0;
            return `
                <tr>
                    <td>
                        <strong>${s.session_date}</strong>
                        ${s.session_time ? `<br><small class="text-muted" style="font-size: 0.78rem;">⏰ ${s.session_time}</small>` : ''}
                    </td>
                    <td><span class="badge badge-outline">${s.course_code}</span> ${s.course_name}</td>
                    <td>${s.title}</td>
                    <td>${s.present_count} / ${s.total_count} Present</td>
                    <td>
                        <span class="badge ${pct >= 75 ? 'badge-present' : 'badge-outline'}">${pct}%</span>
                    </td>
                    <td>
                        <button class="btn btn-outline btn-sm" onclick="openSessionInAttendance(${s.id})">
                            Open in Attendance →
                        </button>
                    </td>
                </tr>
            `;
        }).join('');
    } catch (err) {
        console.error('Error loading sessions table:', err);
    }
}

el.filterSessionCourse.addEventListener('change', loadSessionsTable);

window.openSessionInAttendance = function(sessionId) {
    switchTab('take-attendance');
    el.sessionSelect.value = sessionId;
    onSessionSelected(sessionId);
};

// Create Session Form
if (el.btnAutodetectDatetime) {
    el.btnAutodetectDatetime.addEventListener('click', () => {
        autoDetectSessionDateTime();
        showToast('Auto-detected current date & time');
    });
}

el.btnOpenCreateSessionModal.addEventListener('click', () => {
    autoDetectSessionDateTime();
    openModal('modal-create-session');
});

el.formCreateSession.addEventListener('submit', async (e) => {
    e.preventDefault();
    const payload = {
        course_id: parseInt(el.newSessionCourse.value),
        title: el.newSessionTitle.value,
        session_date: el.newSessionDate.value,
        session_time: el.newSessionTime ? el.newSessionTime.value : ''
    };

    try {
        const res = await fetch('/api/sessions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Could not create session');
        }

        const data = await res.json();
        closeModal('modal-create-session');
        el.formCreateSession.reset();
        showToast('Class Session scheduled successfully!');
        
        await loadSessions(data.session_id);
        if (state.currentTab === 'sessions') {
            loadSessionsTable();
        }
    } catch (err) {
        showToast(err.message, 'error');
    }
});

// ======================= STUDENT PORTAL TAB ======================= //

el.studentPortalSelect.addEventListener('change', (e) => {
    if (e.target.value) {
        el.studentPortalSearch.value = e.target.value;
        fetchStudentStats(e.target.value);
    }
});

el.btnFetchStudentStats.addEventListener('click', () => {
    const roll = el.studentPortalSearch.value.trim();
    if (!roll) {
        showToast('Please enter or select a Roll Number', 'error');
        return;
    }
    fetchStudentStats(roll);
});

el.studentPortalSearch.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        e.preventDefault();
        el.btnFetchStudentStats.click();
    }
});

async function fetchStudentStats(rollNo) {
    try {
        const res = await fetch(`/api/student/${encodeURIComponent(rollNo)}/stats`);
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Student not found');
        }

        const data = await res.json();
        renderStudentPortal(data);
    } catch (err) {
        showToast(err.message, 'error');
        el.studentResultsView.style.display = 'none';
    }
}

let currentPortalRoll = '';

if (el.btnShowStudentQr) {
    el.btnShowStudentQr.addEventListener('click', () => {
        if (!currentPortalRoll) return;
        const host = window.location.host;
        const protocol = window.location.protocol;
        const studentUrl = `${protocol}//${host}/?roll=${encodeURIComponent(currentPortalRoll)}`;
        
        if (el.qrCodeUrl) el.qrCodeUrl.textContent = studentUrl;
        if (el.qrCodeDisplay) {
            const qrApiUrl = `https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(studentUrl)}&margin=4`;
            el.qrCodeDisplay.innerHTML = `<img src="${qrApiUrl}" alt="Student QR" width="180" height="180" style="border-radius:8px; border:2px solid #334155; background:#fff; padding:6px;">`;
        }
        openModal('modal-qr-code');
    });
}

function renderStudentPortal(data) {
    const s = data.student;
    currentPortalRoll = s.roll_no;
    el.studentResultsView.style.display = 'block';

    // Profile Details
    el.portalName.textContent = s.name;
    el.portalRoll.textContent = `ROLL: ${s.roll_no}`;
    el.portalBranch.textContent = `BRANCH: ${s.branch}`;
    
    if (s.photo_path) {
        el.portalAvatar.innerHTML = `<img src="/${s.photo_path}">`;
    } else {
        el.portalAvatar.innerHTML = `<span>👤</span>`;
    }

    // Overall Score
    el.portalOverallPct.textContent = `${data.overall_percentage}%`;
    const isEligible = data.overall_percentage >= 75.0;
    el.portalOverallPct.style.color = isEligible ? '#4ade80' : '#f87171';
    el.portalEligibilityTag.textContent = isEligible ? 'ATTENDANCE ELIGIBLE (≥75%)' : 'ATTENDANCE SHORTAGE (<75%)';
    el.portalEligibilityTag.className = `attendance-status-tag ${isEligible ? '' : 'shortage'}`;

    // Subject Breakdown Cards
    el.portalCoursesGrid.innerHTML = data.courses.map(c => {
        const isGood = c.percentage >= 75.0;
        return `
        <div class="course-metric-card">
            <div class="course-card-top">
                <div>
                    <span class="course-code">${c.code}</span>
                    <h4>${c.name}</h4>
                </div>
                <div class="course-pct" style="color: ${isGood ? '#4ade80' : '#f87171'};">${c.percentage}%</div>
            </div>
            <div class="progress-track">
                <div class="progress-fill ${isGood ? '' : 'shortage'}" style="width: ${c.percentage}%;"></div>
            </div>
            <div class="course-card-bottom">
                <span>Classes Attended</span>
                <span>${c.attended_sessions} / ${c.total_sessions}</span>
            </div>
        </div>
        `;
    }).join('');

    // History Table
    if (data.history.length === 0) {
        el.portalHistoryTbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">No attendance logs found</td></tr>`;
    } else {
        el.portalHistoryTbody.innerHTML = data.history.map(h => `
            <tr>
                <td><strong>${h.session_date}</strong></td>
                <td><span class="badge badge-outline">${h.course_code}</span> ${h.course_name}</td>
                <td>${h.session_title}</td>
                <td>
                    <span class="badge ${h.status === 'Present' ? 'badge-present' : 'badge-absent'}">
                        ${h.status}
                    </span>
                </td>
                <td><span class="text-muted">${h.marked_method || 'Initial'}</span></td>
                <td><span class="text-muted">${h.marked_at ? h.marked_at.split(' ')[1] : '-'}</span></td>
            </tr>
        `).join('');
    }
}

// ======================= STUDENT REGISTRATION ======================= //

el.btnSrcUpload.addEventListener('click', () => {
    el.btnSrcUpload.classList.add('active');
    el.btnSrcCamera.classList.remove('active');
    el.srcUploadBox.style.display = 'block';
    el.srcCameraBox.style.display = 'none';
    stopRegCamera();
});

el.btnSrcCamera.addEventListener('click', async () => {
    el.btnSrcCamera.classList.add('active');
    el.btnSrcUpload.classList.remove('active');
    el.srcUploadBox.style.display = 'none';
    el.srcCameraBox.style.display = 'block';
    startRegCamera();
});

async function startRegCamera() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        showToast('Webcam streaming requires HTTPS or localhost on Android Chrome. Please use "Upload Photo" to select or snap photos from phone camera!', 'error');
        if (el.btnSrcUpload) el.btnSrcUpload.click();
        return;
    }

    try {
        state.regCamStream = await navigator.mediaDevices.getUserMedia({
            video: { width: 480, height: 480, facingMode: state.regFacingMode || 'user' }
        });
        el.regCamVideo.srcObject = state.regCamStream;
        el.regCamVideo.classList.toggle('reg-cam-mirrored', (state.regFacingMode || 'user') === 'user');
    } catch (err) {
        showToast('Camera access denied: ' + err.message, 'error');
    }
}

function stopRegCamera() {
    if (state.regCamStream) {
        state.regCamStream.getTracks().forEach(t => t.stop());
        state.regCamStream = null;
    }
    el.regCamVideo.srcObject = null;
    el.regCamVideo.classList.remove('reg-cam-mirrored');
}

if (el.btnRegFlipCamera) {
    el.btnRegFlipCamera.addEventListener('click', () => {
        state.regFacingMode = (state.regFacingMode === 'user') ? 'environment' : 'user';
        showToast(`Registration camera: ${state.regFacingMode === 'user' ? 'Front (Selfie)' : 'Rear (Portrait)'}`);
        if (state.regCamStream) {
            stopRegCamera();
            startRegCamera();
        }
    });
}

state.regSelectedPhotos = [];

function renderRegGallery() {
    if (!el.regPhotosGallery) return;
    if (state.regSelectedPhotos.length === 0) {
        el.regPreviewBox.style.display = 'none';
        return;
    }
    el.regPreviewBox.style.display = 'block';
    el.regPreviewLabel.textContent = `Selected Photos (${state.regSelectedPhotos.length}):`;
    el.regPhotosGallery.innerHTML = state.regSelectedPhotos.map((item, idx) => `
        <div class="reg-thumb-wrap">
            <img src="${item.url}">
            <button type="button" class="reg-thumb-del" onclick="removeRegPhoto(${idx})" title="Remove photo">✕</button>
        </div>
    `).join('');
}

window.removeRegPhoto = function(idx) {
    state.regSelectedPhotos.splice(idx, 1);
    renderRegGallery();
};

if (el.btnClearRegPhotos) {
    el.btnClearRegPhotos.addEventListener('click', () => {
        state.regSelectedPhotos = [];
        el.regPhotoFile.value = '';
        renderRegGallery();
    });
}

el.btnRegSnap.addEventListener('click', () => {
    const video = el.regCamVideo;
    if (video.videoWidth === 0) return;

    const canvas = el.regCamCanvas;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const dataUrl = canvas.toDataURL('image/jpeg', 0.9);
    state.regSelectedPhotos.push({
        type: 'b64',
        data: dataUrl,
        url: dataUrl
    });
    renderRegGallery();
    showToast(`Snapshot ${state.regSelectedPhotos.length} captured!`);
});

el.regPhotoFile.addEventListener('change', async (e) => {
    if (e.target.files && e.target.files.length > 0) {
        const files = Array.from(e.target.files);
        for (const file of files) {
            try {
                const optFile = await optimizeImageForUpload(file, 1600);
                const reader = new FileReader();
                reader.onload = (ev) => {
                    state.regSelectedPhotos.push({
                        type: 'file',
                        data: optFile,
                        url: ev.target.result
                    });
                    renderRegGallery();
                };
                reader.readAsDataURL(optFile);
            } catch (err) {
                const reader = new FileReader();
                reader.onload = (ev) => {
                    state.regSelectedPhotos.push({
                        type: 'file',
                        data: file,
                        url: ev.target.result
                    });
                    renderRegGallery();
                };
                reader.readAsDataURL(file);
            }
        }
    }
});

el.studentRegForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const roll = el.regRoll.value.trim();
    const name = el.regName.value.trim();
    const branch = el.regBranch.value.trim();

    if (state.regSelectedPhotos.length === 0) {
        showToast('Please select or snap at least one photo for enrollment', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('roll_no', roll);
    formData.append('name', name);
    formData.append('branch', branch);

    const b64List = [];
    state.regSelectedPhotos.forEach(p => {
        if (p.type === 'file') {
            formData.append('photos', p.data);
        } else if (p.type === 'b64') {
            b64List.push(p.data);
        }
    });

    if (b64List.length > 0) {
        formData.append('photos_b64', JSON.stringify(b64List));
    }

    const submitBtn = document.getElementById('btn-submit-registration');
    submitBtn.disabled = true;
    submitBtn.textContent = `Extracting ${state.regSelectedPhotos.length} Facial Vectors & Registering...`;

    try {
        const res = await fetch('/api/students', {
            method: 'POST',
            body: formData
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Registration failed');
        }

        const data = await res.json();
        showToast(data.message || 'Student registered successfully!');
        
        el.studentRegForm.reset();
        state.regSelectedPhotos = [];
        renderRegGallery();
        stopRegCamera();
        el.btnSrcUpload.click();

        await loadStudents();
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Complete Facial Enrollment';
    }
});

// ======================= ADD EXTRA PHOTOS MODAL ======================= //

window.openAddPhotosModal = function(studentId, name, rollNo) {
    if (el.addPhotosStudentId) el.addPhotosStudentId.value = studentId;
    if (el.addPhotosModalTitle) el.addPhotosModalTitle.textContent = `Add Extra Photos: ${name}`;
    if (el.addPhotosModalSubtitle) el.addPhotosModalSubtitle.textContent = `Roll No: ${rollNo} • Upload multiple angles to enhance recognition`;
    if (el.addExtraFiles) el.addExtraFiles.value = '';
    openModal('modal-add-photos');
};

if (el.formAddPhotos) {
    el.formAddPhotos.addEventListener('submit', async (e) => {
        e.preventDefault();
        const studentId = el.addPhotosStudentId.value;
        const files = el.addExtraFiles.files;

        if (!files || files.length === 0) {
            showToast('Please select at least one photo', 'error');
            return;
        }

        const formData = new FormData();
        for (const f of Array.from(files)) {
            const opt = await optimizeImageForUpload(f, 1600);
            formData.append('photos', opt);
        }

        const btn = document.getElementById('btn-submit-extra-photos');
        btn.disabled = true;
        btn.textContent = 'Extracting Embeddings...';

        try {
            const res = await fetch(`/api/students/${studentId}/add-photos`, {
                method: 'POST',
                body: formData
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Failed to add photos');
            }

            const data = await res.json();
            showToast(data.message || 'Photos added successfully!');
            closeModal('modal-add-photos');
            loadStudents();
        } catch (err) {
            showToast(err.message, 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = 'Upload & Add Embeddings';
        }
    });
}

// ======================= COURSES TAB & ROSTER MANAGEMENT ======================= //

state.currentManageCourseId = null;

window.openCourseRosterModal = async function(courseId) {
    state.currentManageCourseId = courseId;
    try {
        const [repRes, unRes] = await Promise.all([
            fetch(`/api/courses/${courseId}/report`),
            fetch(`/api/courses/${courseId}/unenrolled-students`)
        ]);

        if (!repRes.ok) throw new Error("Failed to load course details");
        const report = await repRes.json();
        const unenrolled = unRes.ok ? await unRes.json() : [];

        const course = report.course;
        el.rosterModalTitle.textContent = `${course.code}: ${course.name}`;
        el.rosterModalSubtitle.textContent = `${course.branch} • ${report.sessions.length} total sessions conducted`;

        // Update download buttons
        el.btnModalCourseExcel.href = `/api/export/course/excel?course_id=${courseId}`;
        el.btnModalCourseCsv.href = `/api/export/course/csv?course_id=${courseId}`;

        // Populate unenrolled students
        if (unenrolled.length === 0) {
            el.selectUnenrolledStudent.innerHTML = `<option value="">-- All registered students are already enrolled --</option>`;
            el.btnDoEnrollStudent.disabled = true;
        } else {
            el.selectUnenrolledStudent.innerHTML = `<option value="">-- Choose Student to Enroll (${unenrolled.length} available) --</option>` +
                unenrolled.map(s => `<option value="${s.id}">${s.roll_no} - ${s.name} (${s.branch})</option>`).join('');
            el.btnDoEnrollStudent.disabled = false;
        }

        // Populate enrolled students list
        const students = report.students;
        if (students.length === 0) {
            el.courseRosterTbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">No students enrolled yet. Select a student above to enroll them.</td></tr>`;
        } else {
            el.courseRosterTbody.innerHTML = students.map(s => {
                const isGood = s.percentage >= 75.0;
                return `
                <tr>
                    <td><strong>${s.roll_no}</strong></td>
                    <td>${s.name}</td>
                    <td>${s.attended_sessions} / ${s.total_sessions}</td>
                    <td>
                        <span class="badge ${isGood ? 'badge-present' : 'badge-absent'}">
                            ${s.percentage}%
                        </span>
                    </td>
                    <td>
                        <span class="attendance-status-tag ${isGood ? '' : 'shortage'}" style="margin: 0; font-size: 10px;">
                            ${isGood ? 'ELIGIBLE' : 'SHORTAGE'}
                        </span>
                    </td>
                    <td>
                        <button class="btn-danger-outline" onclick="unenrollStudentFromCourse(${s.student_id}, '${s.name.replace(/'/g, "\\'")}')">
                            ✕ Remove
                        </button>
                    </td>
                </tr>
                `;
            }).join('');
        }

        openModal('modal-manage-roster');
    } catch (err) {
        console.error(err);
        showToast(err.message, 'error');
    }
};

window.unenrollStudentFromCourse = async function(studentId, studentName) {
    if (!state.currentManageCourseId) return;
    const confirmed = await showConfirm(
        'Remove Student from Course',
        `Remove "${studentName}" from this course? Their attendance records for this course will also be deleted.`
    );
    if (!confirmed) return;

    try {
        const res = await fetch(`/api/courses/${state.currentManageCourseId}/unenroll`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ student_id: studentId })
        });
        if (res.ok) {
            showToast(`${studentName} removed from course`);
            openCourseRosterModal(state.currentManageCourseId);
            loadCourses();
        } else {
            showToast('Failed to unenroll student', 'error');
        }
    } catch (err) {
        showToast(err.message, 'error');
    }
};

el.btnDoEnrollStudent.addEventListener('click', async () => {
    const studentId = el.selectUnenrolledStudent.value;
    if (!studentId || !state.currentManageCourseId) {
        showToast('Please select a student to enroll', 'error');
        return;
    }
     
    try {
        const res = await fetch(`/api/courses/${state.currentManageCourseId}/enroll`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ student_id: parseInt(studentId) })
        });
        if (res.ok) {
            showToast('Student successfully enrolled in course!');
            openCourseRosterModal(state.currentManageCourseId);
            loadCourses();
        } else {
            showToast('Enrollment failed', 'error');
        }
    } catch (err) {
        showToast(err.message, 'error');
    }
});

el.btnOpenCreateCourseModal.addEventListener('click', () => {
    openModal('modal-create-course');
});

el.formCreateCourse.addEventListener('submit', async (e) => {
    e.preventDefault();
    const payload = {
        code: el.newCourseCode.value.trim(),
        name: el.newCourseName.value.trim(),
        branch: el.newCourseBranch.value.trim()
    };

    try {
        const res = await fetch('/api/courses', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Failed to create course');
        }

        closeModal('modal-create-course');
        el.formCreateCourse.reset();
        showToast('Course added successfully!');
        loadCourses();
    } catch (err) {
        showToast(err.message, 'error');
    }
});

window.deleteCourse = async function(courseId, courseCode, courseName) {
    const confirmed = await showConfirm(
        `Delete Course: ${courseCode}`,
        `Permanently delete "${courseCode}: ${courseName}"?\n\nThis will also delete all its sessions, attendance records, and student enrollments. This cannot be undone.`
    );
    if (!confirmed) return;

    try {
        const res = await fetch(`/api/courses/${courseId}`, {
            method: 'DELETE'
        });
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || 'Failed to delete course');
        }

        showToast(data.message || `Course ${courseCode} deleted successfully`);
        closeModal('modal-manage-roster');
        
        await loadCourses();
        await loadSessions();

        // If the active attendance session was from this course, refresh it
        if (state.selectedSessionId) {
            const currentSession = state.sessions.find(s => s.id === state.selectedSessionId);
            if (!currentSession) {
                if (state.sessions.length > 0) {
                    el.sessionSelect.value = state.sessions[0].id;
                    onSessionSelected(state.sessions[0].id);
                } else {
                    el.sessionSelect.value = '';
                    onSessionSelected(null);
                }
            }
        }
    } catch (err) {
        showToast(err.message, 'error');
    }
};

window.deleteCourseFromModal = function() {
    if (!state.currentManageCourseId) return;
    const course = state.courses.find(c => c.id === state.currentManageCourseId);
    const code = course ? course.code : 'this course';
    const name = course ? course.name : '';
    deleteCourse(state.currentManageCourseId, code, name);
};

// ======================= MODAL UTILITIES ======================= //

function openModal(id) {
    const modal = document.getElementById(id);
    if (modal) modal.style.display = 'flex';
}

function closeModal(id) {
    const modal = document.getElementById(id);
    if (modal) modal.style.display = 'none';
}

document.querySelectorAll('[data-close]').forEach(btn => {
    btn.addEventListener('click', () => closeModal(btn.dataset.close));
});

window.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-backdrop')) {
        e.target.style.display = 'none';
    }
});

async function loadNetworkInfo() {
    try {
        const res = await fetch('/api/network-info');
        if (res.ok) {
            const data = await res.json();
            if (el.mobileIpLink) {
                el.mobileIpLink.href = data.mobile_url;
                el.mobileIpLink.textContent = data.mobile_url.replace('http://', '');
            }
        }
    } catch (e) {
        console.log('Network info fetch skipped:', e);
    }
}

// ======================= INITIALIZATION ======================= //

window.addEventListener('DOMContentLoaded', async () => {
    await loadCourses();
    await loadSessions();
    await loadStudents();
    loadNetworkInfo();

    // Auto-search from QR code or direct link: ?roll=2024CS001
    const urlParams = new URLSearchParams(window.location.search);
    const rollParam = urlParams.get('roll');
    if (rollParam) {
        switchTab('student-portal');
        if (el.studentPortalSearch) el.studentPortalSearch.value = rollParam;
        fetchStudentStats(rollParam);
    }
});
