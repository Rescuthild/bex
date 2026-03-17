# BEX Coffee v2 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** BEX Coffee'yi localStorage tabanli tek HTML'den, FastAPI + SQLite backend'li, mudur/calisan rol ayrimli, log tutan bir web uygulamasina donusturmek.

**Architecture:** FastAPI backend SQLite ile veri tutar ve REST API sunar. Iki statik HTML (calisan/admin) API'ye fetch ile baglanir. Timer mantigi frontend'de kalir (deadline-based). Admin token URL'de tasindigi icin middleware ile dogrulanir.

**Tech Stack:** Python 3.11, FastAPI, uvicorn, SQLite3, vanilla HTML/CSS/JS

**Spec:** `docs/superpowers/specs/2026-03-18-bex-v2-design.md`

---

## Chunk 1: Backend Foundation

### Task 1: Project scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `database.py`
- Create: `models.py`
- Create: `main.py`
- Modify: `Dockerfile`
- Create: `static/` directory

- [ ] **Step 1: Create requirements.txt**

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
```

- [ ] **Step 2: Create database.py with schema init**

```python
import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.environ.get("DB_PATH", "/app/data/bex.db")

def get_db_path():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return DB_PATH

@contextmanager
def get_db():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS areas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                interval_min INTEGER NOT NULL DEFAULT 30,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS staff (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS shifts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                staff_id INTEGER NOT NULL REFERENCES staff(id) ON DELETE CASCADE,
                day_of_week INTEGER NOT NULL CHECK(day_of_week BETWEEN 0 AND 6),
                shift_start TEXT NOT NULL,
                shift_end TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                area_id INTEGER NOT NULL REFERENCES areas(id) ON DELETE CASCADE,
                staff_id INTEGER REFERENCES staff(id) ON DELETE SET NULL,
                action TEXT NOT NULL CHECK(action IN ('checked','missed')),
                alarm_time TEXT NOT NULL DEFAULT (datetime('now')),
                confirmed_at TEXT
            );
        """)
```

- [ ] **Step 3: Create models.py with Pydantic schemas**

```python
from pydantic import BaseModel
from typing import Optional

class AreaCreate(BaseModel):
    name: str
    interval_min: int = 30

class AreaUpdate(BaseModel):
    name: Optional[str] = None
    interval_min: Optional[int] = None

class AreaOut(BaseModel):
    id: int
    name: str
    interval_min: int

class StaffCreate(BaseModel):
    name: str

class StaffOut(BaseModel):
    id: int
    name: str

class ShiftCreate(BaseModel):
    staff_id: int
    day_of_week: int
    shift_start: str
    shift_end: str

class ShiftOut(BaseModel):
    id: int
    staff_id: int
    staff_name: str
    day_of_week: int
    shift_start: str
    shift_end: str

class LogCreate(BaseModel):
    area_id: int
    staff_id: Optional[int] = None

class LogOut(BaseModel):
    id: int
    area_id: int
    area_name: str
    staff_id: Optional[int]
    staff_name: Optional[str]
    action: str
    alarm_time: str
    confirmed_at: Optional[str]
```

- [ ] **Step 4: Create main.py with FastAPI app skeleton**

```python
import os
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from database import init_db, get_db
from models import (
    AreaCreate, AreaUpdate, AreaOut,
    StaffCreate, StaffOut,
    ShiftCreate, ShiftOut,
    LogCreate, LogOut,
)

app = FastAPI(title="BEX Coffee")

ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "dev-token-change-me")

@app.on_event("startup")
def startup():
    init_db()

def verify_token(token: str):
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=404)

# --- Public API ---

@app.get("/api/areas", response_model=list[AreaOut])
def list_areas():
    with get_db() as conn:
        rows = conn.execute("SELECT id, name, interval_min FROM areas ORDER BY id").fetchall()
        return [dict(r) for r in rows]

@app.get("/api/staff/active", response_model=list[StaffOut])
def active_staff():
    now = datetime.now()
    day = now.weekday()
    # Python weekday: 0=Mon. JS weekday: 0=Sun. Convert.
    js_day = (day + 1) % 7
    cur_time = now.strftime("%H:%M")
    with get_db() as conn:
        rows = conn.execute("""
            SELECT DISTINCT s.id, s.name FROM staff s
            JOIN shifts sh ON s.id = sh.staff_id
            WHERE sh.day_of_week = ?
            AND sh.shift_start <= ? AND sh.shift_end > ?
        """, (js_day, cur_time, cur_time)).fetchall()
        return [dict(r) for r in rows]

@app.get("/api/shifts/today")
def shifts_today():
    now = datetime.now()
    js_day = (now.weekday() + 1) % 7
    with get_db() as conn:
        rows = conn.execute("""
            SELECT sh.id, sh.staff_id, s.name as staff_name,
                   sh.day_of_week, sh.shift_start, sh.shift_end
            FROM shifts sh JOIN staff s ON sh.staff_id = s.id
            WHERE sh.day_of_week = ? ORDER BY sh.shift_start
        """, (js_day,)).fetchall()
        return [dict(r) for r in rows]

@app.post("/api/logs")
def create_log(log: LogCreate):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO logs (area_id, staff_id, action, alarm_time, confirmed_at) VALUES (?, ?, 'checked', datetime('now'), datetime('now'))",
            (log.area_id, log.staff_id)
        )
        return {"ok": True}

# --- Admin API ---

@app.get("/api/admin/{token}/areas", response_model=list[AreaOut])
def admin_list_areas(token: str):
    verify_token(token)
    return list_areas()

@app.post("/api/admin/{token}/areas", response_model=AreaOut)
def admin_create_area(token: str, area: AreaCreate):
    verify_token(token)
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO areas (name, interval_min) VALUES (?, ?)",
            (area.name, area.interval_min)
        )
        return {"id": cur.lastrowid, "name": area.name, "interval_min": area.interval_min}

@app.patch("/api/admin/{token}/areas/{area_id}", response_model=AreaOut)
def admin_update_area(token: str, area_id: int, area: AreaUpdate):
    verify_token(token)
    with get_db() as conn:
        existing = conn.execute("SELECT * FROM areas WHERE id = ?", (area_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404)
        name = area.name if area.name is not None else existing["name"]
        interval = area.interval_min if area.interval_min is not None else existing["interval_min"]
        conn.execute("UPDATE areas SET name=?, interval_min=? WHERE id=?", (name, interval, area_id))
        return {"id": area_id, "name": name, "interval_min": interval}

@app.delete("/api/admin/{token}/areas/{area_id}")
def admin_delete_area(token: str, area_id: int):
    verify_token(token)
    with get_db() as conn:
        conn.execute("DELETE FROM areas WHERE id = ?", (area_id,))
        return {"ok": True}

@app.get("/api/admin/{token}/staff", response_model=list[StaffOut])
def admin_list_staff(token: str):
    verify_token(token)
    with get_db() as conn:
        rows = conn.execute("SELECT id, name FROM staff ORDER BY id").fetchall()
        return [dict(r) for r in rows]

@app.post("/api/admin/{token}/staff", response_model=StaffOut)
def admin_create_staff(token: str, s: StaffCreate):
    verify_token(token)
    with get_db() as conn:
        cur = conn.execute("INSERT INTO staff (name) VALUES (?)", (s.name,))
        return {"id": cur.lastrowid, "name": s.name}

@app.delete("/api/admin/{token}/staff/{staff_id}")
def admin_delete_staff(token: str, staff_id: int):
    verify_token(token)
    with get_db() as conn:
        conn.execute("DELETE FROM staff WHERE id = ?", (staff_id,))
        return {"ok": True}

@app.get("/api/admin/{token}/shifts")
def admin_list_shifts(token: str):
    verify_token(token)
    with get_db() as conn:
        rows = conn.execute("""
            SELECT sh.id, sh.staff_id, s.name as staff_name,
                   sh.day_of_week, sh.shift_start, sh.shift_end
            FROM shifts sh JOIN staff s ON sh.staff_id = s.id
            ORDER BY sh.day_of_week, sh.shift_start
        """).fetchall()
        return [dict(r) for r in rows]

@app.post("/api/admin/{token}/shifts")
def admin_create_shift(token: str, shift: ShiftCreate):
    verify_token(token)
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO shifts (staff_id, day_of_week, shift_start, shift_end) VALUES (?,?,?,?)",
            (shift.staff_id, shift.day_of_week, shift.shift_start, shift.shift_end)
        )
        staff = conn.execute("SELECT name FROM staff WHERE id=?", (shift.staff_id,)).fetchone()
        return {"id": cur.lastrowid, "staff_id": shift.staff_id, "staff_name": staff["name"],
                "day_of_week": shift.day_of_week, "shift_start": shift.shift_start, "shift_end": shift.shift_end}

@app.delete("/api/admin/{token}/shifts/{shift_id}")
def admin_delete_shift(token: str, shift_id: int):
    verify_token(token)
    with get_db() as conn:
        conn.execute("DELETE FROM shifts WHERE id = ?", (shift_id,))
        return {"ok": True}

@app.get("/api/admin/{token}/logs")
def admin_list_logs(token: str, date: str = None, area_id: int = None):
    verify_token(token)
    query = """
        SELECT l.id, l.area_id, a.name as area_name,
               l.staff_id, s.name as staff_name,
               l.action, l.alarm_time, l.confirmed_at
        FROM logs l
        LEFT JOIN areas a ON l.area_id = a.id
        LEFT JOIN staff s ON l.staff_id = s.id
        WHERE 1=1
    """
    params = []
    if date:
        query += " AND date(l.alarm_time) = ?"
        params.append(date)
    if area_id:
        query += " AND l.area_id = ?"
        params.append(area_id)
    query += " ORDER BY l.alarm_time DESC LIMIT 500"
    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

# --- Page routes ---

@app.get("/", response_class=HTMLResponse)
def serve_index():
    return FileResponse("static/index.html")

@app.get("/admin/{token}", response_class=HTMLResponse)
def serve_admin(token: str):
    verify_token(token)
    return FileResponse("static/admin.html")

app.mount("/static", StaticFiles(directory="static"), name="static")
```

- [ ] **Step 5: Update Dockerfile**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /app/data
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 6: Move index.html and manifest.json into static/**

```bash
mkdir -p static
mv index.html static/index.html
mv manifest.json static/manifest.json
```

- [ ] **Step 7: Test backend starts locally**

```bash
DB_PATH=./data/bex.db ADMIN_TOKEN=test123 uvicorn main:app --port 8765
# In another terminal:
curl http://localhost:8765/api/areas  # Should return []
curl http://localhost:8765/           # Should return HTML
curl http://localhost:8765/admin/test123  # Should return 404 (admin.html not yet created)
```

- [ ] **Step 8: Commit**

```bash
git add requirements.txt database.py models.py main.py Dockerfile static/
git commit -m "feat: FastAPI backend with SQLite, API endpoints, admin token auth"
```

---

## Chunk 2: Frontend — Calisan Ekrani

### Task 2: Convert index.html to API-backed worker view

**Files:**
- Modify: `static/index.html`

The worker view keeps only the "Kontrol Paneli" tab. Removes all CRUD tabs (Haftalik Vardiya, Alanlar, Personel). Loads data from API on startup.

- [ ] **Step 1: Modify static/index.html**

Key changes to the existing HTML:

1. **Header:** Remove tabs for Vardiya/Alanlar/Personel. Keep only "Kontrol Paneli" and clock.
2. **Remove panes:** Delete `pane-shifts`, `pane-areas`, `pane-personel` sections and their forms.
3. **Remove settings drawer** (ses ayarlari stays — it's useful for workers too).
4. **Replace `defaultState()` and localStorage state** with API fetch:

Replace the state initialization block (`function defaultState()` through `let selectedDay`) with:

```javascript
let state = { staff: [], areas: [], weekSchedule: {} };

async function loadState() {
    const [areasRes, staffRes, shiftsRes] = await Promise.all([
        fetch('/api/areas').then(r => r.json()),
        fetch('/api/staff/active').then(r => r.json()),
        fetch('/api/shifts/today').then(r => r.json()),
    ]);
    state.areas = areasRes;
    state.staff = staffRes;
    // Build weekSchedule for today only
    const today = todayDayIndex();
    state.weekSchedule = {};
    for (let d = 0; d < 7; d++) state.weekSchedule[d] = [];
    state.weekSchedule[today] = shiftsRes.map(s => ({
        id: s.id, staffId: s.staff_id,
        shiftStart: s.shift_start, shiftEnd: s.shift_end
    }));
    initTimers();
    renderPanel();
}
```

5. **Replace `save()` function:** Remove it — no longer saving to localStorage (except timer deadlines).

6. **Modify `confirmAlarm()`:** Add API call to log the check:

```javascript
function confirmAlarm(){
    const item = alarmQueue.shift();
    if (item) {
        fetch('/api/logs', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({area_id: item.areaId, staff_id: item.assignedStaffId})
        }).catch(()=>{});
    }
    if(alarmQueue.length>0){
        playAlarm();
        showNextAlarm();
    } else {
        alarmOpen=false;
        document.getElementById('overlay').classList.remove('show');
    }
}
```

7. **On page load:** Call `loadState()` instead of reading from localStorage. Periodically refresh active staff (every 5 min).

```javascript
// --- INIT ---
loadState();
setInterval(loadState, 300000); // Refresh data every 5 minutes
```

- [ ] **Step 2: Test worker view**

```bash
DB_PATH=./data/bex.db ADMIN_TOKEN=test123 uvicorn main:app --port 8765
# Open http://localhost:8765/ in browser
# Should show empty timer grid ("Henuz alan eklenmedi")
# Add test data via API:
curl -X POST http://localhost:8765/api/admin/test123/areas -H "Content-Type: application/json" -d '{"name":"Bar Tezgahi","interval_min":30}'
curl -X POST http://localhost:8765/api/admin/test123/staff -H "Content-Type: application/json" -d '{"name":"Ayse K."}'
# Refresh page — should show timer
```

- [ ] **Step 3: Commit**

```bash
git add static/index.html
git commit -m "feat: worker view — API-backed timers, removed CRUD tabs"
```

---

## Chunk 3: Frontend — Admin Panel

### Task 3: Create admin.html with full management + logs

**Files:**
- Create: `static/admin.html`

Admin panel is the full current interface (all tabs) plus a new "Loglar" tab. All CRUD operations go through the admin API.

- [ ] **Step 1: Create static/admin.html**

Copy the original `index.html` structure (before worker simplification) as the starting point. Then modify:

1. **Header tabs:** Kontrol Paneli | Haftalik Vardiya | Alanlar | Personel | **Loglar**
2. **Extract admin token from URL:** `const ADMIN_TOKEN = window.location.pathname.split('/admin/')[1];`
3. **API helper:**

```javascript
const API = `/api/admin/${ADMIN_TOKEN}`;
async function api(path, opts = {}) {
    const res = await fetch(API + path, {
        headers: {'Content-Type': 'application/json'},
        ...opts
    });
    if (!res.ok) throw new Error(res.status);
    return res.json();
}
```

4. **Replace all CRUD functions** to use API instead of localStorage:

```javascript
// Areas
async function loadAreas() { state.areas = await api('/areas'); }
async function addArea() {
    const name = document.getElementById('new-aname').value.trim();
    const intervalMin = parseInt(document.getElementById('new-amin').value) || 30;
    if (!name) { alert('Alan adi giriniz'); return; }
    await api('/areas', { method: 'POST', body: JSON.stringify({name, interval_min: intervalMin}) });
    document.getElementById('new-aname').value = '';
    await loadAreas();
    renderAreas();
    renderTimerGrid();
}
async function deleteArea(id) {
    await api(`/areas/${id}`, { method: 'DELETE' });
    delete timers[id];
    await loadAreas();
    renderAreas();
    if (activeTab === 'panel') renderTimerGrid();
}
async function saveInterval(areaId) {
    const val = parseInt(document.getElementById('imin-' + areaId).value);
    if (!val || val < 1) { alert('Gecerli bir deger giriniz'); return; }
    await api(`/areas/${areaId}`, { method: 'PATCH', body: JSON.stringify({interval_min: val}) });
    timers[areaId] = {deadline: Date.now() + val*60*1000, total: val*60};
    saveTimers();
    await loadAreas();
    if (activeTab === 'panel') renderTimerGrid();
}

// Staff
async function loadStaff() { state.staff = await api('/staff'); }
async function addPersonel() {
    const name = document.getElementById('new-pname').value.trim();
    if (!name) { alert('Ad giriniz'); return; }
    await api('/staff', { method: 'POST', body: JSON.stringify({name}) });
    document.getElementById('new-pname').value = '';
    await loadStaff();
    renderPersonel();
}
async function deletePersonel(id) {
    await api(`/staff/${id}`, { method: 'DELETE' });
    await loadStaff();
    await loadShifts();
    renderPersonel();
}

// Shifts
async function loadShifts() {
    const all = await api('/shifts');
    state.weekSchedule = {};
    for (let d = 0; d < 7; d++) state.weekSchedule[d] = [];
    all.forEach(s => {
        state.weekSchedule[s.day_of_week].push({
            id: s.id, staffId: s.staff_id, staffName: s.staff_name,
            shiftStart: s.shift_start, shiftEnd: s.shift_end
        });
    });
}
async function addShiftEntry() {
    const staffId = parseInt(document.getElementById('sh-staff').value);
    if (!staffId) { alert('Personel seciniz'); return; }
    await api('/shifts', { method: 'POST', body: JSON.stringify({
        staff_id: staffId, day_of_week: selectedDay,
        shift_start: document.getElementById('sh-start').value,
        shift_end: document.getElementById('sh-end').value
    })});
    await loadShifts();
    buildDayTabs();
    renderShifts();
}
async function deleteShiftEntry(id) {
    await api(`/shifts/${id}`, { method: 'DELETE' });
    await loadShifts();
    buildDayTabs();
    renderShifts();
}
```

5. **Loglar sekmesi (yeni):**

HTML pane:
```html
<div id="pane-logs" class="tab-pane">
    <div class="card" style="overflow:hidden">
        <div class="card-hd">
            <span class="card-title">Kontrol Loglari</span>
            <div style="display:flex;gap:8px;align-items:center">
                <input type="date" id="log-date" style="padding:5px 8px;border:1px solid var(--border);border-radius:6px;font-size:12px">
                <select id="log-area" style="padding:5px 8px;border:1px solid var(--border);border-radius:6px;font-size:12px">
                    <option value="">Tum Alanlar</option>
                </select>
                <button class="btn-add" onclick="loadLogs()" style="padding:5px 12px;font-size:12px">Filtrele</button>
                <button class="btn-del" onclick="exportCSV()">CSV</button>
            </div>
        </div>
        <div id="log-summary" style="padding:10px 14px;background:var(--cream);font-size:12px;color:var(--muted)"></div>
        <table>
            <thead><tr><th>Saat</th><th>Alan</th><th>Personel</th><th>Durum</th><th>Onay Suresi</th></tr></thead>
            <tbody id="log-tbody"></tbody>
        </table>
    </div>
</div>
```

Log loading and rendering:
```javascript
let logData = [];
async function loadLogs() {
    const date = document.getElementById('log-date').value;
    const areaId = document.getElementById('log-area').value;
    let url = '/logs?';
    if (date) url += `date=${date}&`;
    if (areaId) url += `area_id=${areaId}&`;
    logData = await api(url);
    renderLogs();
}
function renderLogs() {
    const tbody = document.getElementById('log-tbody');
    if (logData.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:20px">Bu tarihte log yok</td></tr>';
    } else {
        tbody.innerHTML = logData.map(l => {
            const t = new Date(l.alarm_time);
            const saat = t.toLocaleTimeString('tr-TR', {hour:'2-digit',minute:'2-digit'});
            const durum = l.action === 'checked'
                ? '<span style="color:var(--success)">Yapildi</span>'
                : '<span style="color:var(--danger)">Kacirildi</span>';
            let onaySuresi = '-';
            if (l.confirmed_at && l.alarm_time) {
                const diff = Math.round((new Date(l.confirmed_at) - new Date(l.alarm_time)) / 1000);
                onaySuresi = diff < 60 ? diff + 'sn' : Math.round(diff/60) + 'dk';
            }
            return `<tr><td>${saat}</td><td>${l.area_name||'-'}</td><td>${l.staff_name||'-'}</td><td>${durum}</td><td>${onaySuresi}</td></tr>`;
        }).join('');
    }
    // Summary
    const total = logData.length;
    const checked = logData.filter(l => l.action === 'checked').length;
    const missed = total - checked;
    document.getElementById('log-summary').textContent =
        `Toplam: ${total} | Yapildi: ${checked} | Kacirildi: ${missed} | Oran: ${total ? Math.round(checked/total*100) : 0}%`;
}
function exportCSV() {
    if (!logData.length) return;
    const header = 'Saat,Alan,Personel,Durum,Onay Suresi\n';
    const rows = logData.map(l => {
        const t = new Date(l.alarm_time).toLocaleString('tr-TR');
        const dur = l.action === 'checked' ? 'Yapildi' : 'Kacirildi';
        return `${t},${l.area_name||'-'},${l.staff_name||'-'},${dur}`;
    }).join('\n');
    const blob = new Blob([header + rows], {type: 'text/csv'});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `bex-log-${document.getElementById('log-date').value||'all'}.csv`;
    a.click();
}
```

6. **Init:** Load all data from API on page load.

```javascript
async function loadState() {
    await Promise.all([loadAreas(), loadStaff(), loadShifts()]);
    initTimers();
    renderPanel();
    // Set log date to today
    document.getElementById('log-date').value = new Date().toISOString().split('T')[0];
    // Populate area filter
    document.getElementById('log-area').innerHTML = '<option value="">Tum Alanlar</option>' +
        state.areas.map(a => `<option value="${a.id}">${a.name}</option>`).join('');
}
loadState();
```

- [ ] **Step 2: Test admin panel**

```bash
DB_PATH=./data/bex.db ADMIN_TOKEN=test123 uvicorn main:app --port 8765
# Open http://localhost:8765/admin/test123
# Test: Add area, add staff, add shift, trigger alarm, confirm, check logs tab
```

- [ ] **Step 3: Commit**

```bash
git add static/admin.html
git commit -m "feat: admin panel — full CRUD, log viewer, CSV export"
```

---

## Chunk 4: Deploy and Verify

### Task 4: Update Dockerfile and deploy to Coolify

**Files:**
- Modify: `Dockerfile`
- Delete: old root `manifest.json` (moved to static/)

- [ ] **Step 1: Verify Dockerfile is correct**

Ensure Dockerfile copies everything and serves from correct paths.

- [ ] **Step 2: Test Docker build locally**

```bash
docker build -t bex-coffee .
docker run --rm -p 8765:8000 -e ADMIN_TOKEN=test123 -v $(pwd)/data:/app/data bex-coffee
# Test: http://localhost:8765/ (worker)
# Test: http://localhost:8765/admin/test123 (admin)
# Test: http://localhost:8765/api/areas (API)
```

- [ ] **Step 3: Push to GitHub and deploy**

```bash
git push origin master
# Trigger Coolify deploy via API:
curl -s -H "Authorization: Bearer <COOLIFY_TOKEN>" "https://deploy.saviordigital.com/api/v1/deploy?uuid=ow82ix72ykf0n5aa5pcimktj"
```

- [ ] **Step 4: Configure Coolify**

- Set env var: `ADMIN_TOKEN=<gizli-token>`
- Set env var: `DB_PATH=/app/data/bex.db`
- Add volume mount: Coolify persistent storage -> `/app/data`
- Update port: `8000`

- [ ] **Step 5: Verify production**

```bash
curl https://bex.saviordigital.com/api/areas  # Should return []
# Open https://bex.saviordigital.com/ in browser — worker view
# Open https://bex.saviordigital.com/admin/<token> — admin panel
```

- [ ] **Step 6: Commit any final fixes**

```bash
git add -A
git commit -m "chore: deploy config and final fixes"
```

---

## Chunk 5: Seed Data and Smoke Test

### Task 5: Add initial data and end-to-end verification

- [ ] **Step 1: Seed initial data via admin API**

```bash
TOKEN="<admin-token>"
BASE="https://bex.saviordigital.com/api/admin/$TOKEN"

# Areas
curl -X POST "$BASE/areas" -H "Content-Type: application/json" -d '{"name":"Bar Tezgahi","interval_min":30}'
curl -X POST "$BASE/areas" -H "Content-Type: application/json" -d '{"name":"Musteri Tuvaleti","interval_min":15}'
curl -X POST "$BASE/areas" -H "Content-Type: application/json" -d '{"name":"Giris & Vitrin","interval_min":60}'
curl -X POST "$BASE/areas" -H "Content-Type: application/json" -d '{"name":"Masa & Sandalyeler","interval_min":45}'
curl -X POST "$BASE/areas" -H "Content-Type: application/json" -d '{"name":"Mutfak","interval_min":20}'

# Staff
curl -X POST "$BASE/staff" -H "Content-Type: application/json" -d '{"name":"Ayse K."}'
curl -X POST "$BASE/staff" -H "Content-Type: application/json" -d '{"name":"Mehmet D."}'
curl -X POST "$BASE/staff" -H "Content-Type: application/json" -d '{"name":"Zeynep T."}'

# Shifts (sample for today)
# Adjust day_of_week and staff IDs as needed
```

- [ ] **Step 2: E2E smoke test**

1. Open worker view on iPad
2. Wait for alarm or press test button
3. Confirm alarm
4. Open admin panel
5. Check Loglar tab — verify log entry appears with correct area, staff, time
6. Add/remove area from admin — verify worker view updates on next refresh

- [ ] **Step 3: Final commit**

```bash
git add -A && git commit -m "docs: seed data script and smoke test notes"
```
