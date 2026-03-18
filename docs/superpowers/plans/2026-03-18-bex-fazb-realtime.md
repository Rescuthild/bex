# BEX Coffee Faz B — Gercek Zamanli Izleme Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** WebSocket ile mudur canli izleme dashboard'u ve cift yonlu gercek zamanli guncelleme eklemek.

**Architecture:** FastAPI WebSocket endpoint (`/ws`) uzerinden admin ve worker client'lar baglenir. ConnectionManager admin/worker gruplarini ayri tutar. CRUD islemleri sonrasi worker'lara, log kaydi sonrasi admin'lere broadcast yapilir. Mudur paneline alan kartlarini gosteren "Canli Izleme" sekmesi eklenir.

**Tech Stack:** FastAPI WebSocket (ek paket gerekmez), vanilla JS WebSocket API

**Spec:** `docs/superpowers/specs/2026-03-18-bex-fazb-realtime-design.md`

---

## File Map

| Dosya | Degisiklik | Sorumluluk |
|-------|-----------|------------|
| `database.py` | Modify | `delay_threshold_min` migration ekle |
| `models.py` | Modify | Area modellerine `delay_threshold_min` ekle |
| `websocket_manager.py` | Create | ConnectionManager sinifi — baglanti yonetimi ve broadcast |
| `main.py` | Modify | `/ws` endpoint, CRUD endpoint'lerine broadcast ekleme |
| `static/index.html` | Modify | WebSocket baglantisi, config_changed handler, alarm_triggered gonderimi |
| `static/admin.html` | Modify | Canli Izleme sekmesi, WebSocket baglantisi, gecikme ayari |

---

## Chunk 1: Backend WebSocket Altyapisi

### Task 1: Database migration — delay_threshold_min

**Files:**
- Modify: `database.py`
- Modify: `models.py`

- [ ] **Step 1: Add delay_threshold_min to areas table schema in database.py**

In `database.py`, update the SCHEMA string — add `delay_threshold_min` column to the areas CREATE TABLE:

```python
CREATE TABLE IF NOT EXISTS areas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    interval_min INTEGER NOT NULL DEFAULT 30,
    delay_threshold_min INTEGER NOT NULL DEFAULT 5,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

Add a migration function after `init_db()`:

```python
def migrate_db():
    """Run schema migrations for existing databases."""
    with get_db() as db:
        # Check if delay_threshold_min column exists
        cols = [row[1] for row in db.execute("PRAGMA table_info(areas)").fetchall()]
        if "delay_threshold_min" not in cols:
            db.execute("ALTER TABLE areas ADD COLUMN delay_threshold_min INTEGER NOT NULL DEFAULT 5")
```

- [ ] **Step 2: Update Pydantic models in models.py**

Add `delay_threshold_min` to Area models:

```python
class AreaCreate(BaseModel):
    name: str
    interval_min: int = 30
    delay_threshold_min: int = 5

class AreaUpdate(BaseModel):
    name: Optional[str] = None
    interval_min: Optional[int] = None
    delay_threshold_min: Optional[int] = None

class AreaOut(BaseModel):
    id: int
    name: str
    interval_min: int
    delay_threshold_min: int
```

- [ ] **Step 3: Update main.py area queries to include delay_threshold_min**

Every SQL query that reads areas needs to SELECT `delay_threshold_min`:

- `list_areas()`: `SELECT id, name, interval_min, delay_threshold_min FROM areas ORDER BY id`
- `admin_list_areas()`: same
- `admin_create_area()`: include `delay_threshold_min` in INSERT and return
- `admin_update_area()`: include `delay_threshold_min` in UPDATE logic

In `admin_update_area`, add:
```python
new_threshold = body.delay_threshold_min if body.delay_threshold_min is not None else existing["delay_threshold_min"]
db.execute(
    "UPDATE areas SET name = ?, interval_min = ?, delay_threshold_min = ? WHERE id = ?",
    (new_name, new_interval, new_threshold, area_id),
)
return {"id": area_id, "name": new_name, "interval_min": new_interval, "delay_threshold_min": new_threshold}
```

In `admin_create_area`:
```python
cur = db.execute(
    "INSERT INTO areas (name, interval_min, delay_threshold_min) VALUES (?, ?, ?)",
    (body.name, body.interval_min, body.delay_threshold_min),
)
return {"id": area_id, "name": body.name, "interval_min": body.interval_min, "delay_threshold_min": body.delay_threshold_min}
```

- [ ] **Step 4: Call migrate_db() in startup**

In `main.py`, update `on_startup()`:

```python
from database import get_db, init_db, migrate_db

@app.on_event("startup")
def on_startup():
    init_db()
    migrate_db()
```

- [ ] **Step 5: Test migration**

```bash
DB_PATH=./data/bex.db ADMIN_TOKEN=test123 python3 -m uvicorn main:app --port 8765 &
sleep 2
# Create area — should include delay_threshold_min
curl -s -X POST http://localhost:8765/api/admin/test123/areas -H "Content-Type: application/json" -d '{"name":"Test","interval_min":30}'
# Should return: {"id":1,"name":"Test","interval_min":30,"delay_threshold_min":5}
curl -s http://localhost:8765/api/areas
# Should include delay_threshold_min
kill %1; rm -rf ./data
```

- [ ] **Step 6: Commit**

```bash
git add database.py models.py main.py
git commit -m "feat: add delay_threshold_min to areas table"
```

---

### Task 2: WebSocket ConnectionManager

**Files:**
- Create: `websocket_manager.py`

- [ ] **Step 1: Create websocket_manager.py**

```python
import json
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.admin_connections: list[WebSocket] = []
        self.worker_connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket, role: str):
        await ws.accept()
        if role == "admin":
            self.admin_connections.append(ws)
        else:
            self.worker_connections.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.admin_connections:
            self.admin_connections.remove(ws)
        if ws in self.worker_connections:
            self.worker_connections.remove(ws)

    async def broadcast_admins(self, data: dict):
        message = json.dumps(data)
        dead = []
        for ws in self.admin_connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def broadcast_workers(self, data: dict):
        message = json.dumps(data)
        dead = []
        for ws in self.worker_connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

manager = ConnectionManager()
```

- [ ] **Step 2: Commit**

```bash
git add websocket_manager.py
git commit -m "feat: WebSocket ConnectionManager with admin/worker groups"
```

---

### Task 3: WebSocket endpoint and broadcast integration in main.py

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Add WebSocket endpoint**

Add imports and the `/ws` endpoint:

```python
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from websocket_manager import manager
import json

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    # Wait for registration message
    await ws.accept()
    try:
        reg = await ws.receive_text()
        data = json.loads(reg)
        role = data.get("role", "worker")
    except Exception:
        role = "worker"

    if role == "admin":
        manager.admin_connections.append(ws)
    else:
        manager.worker_connections.append(ws)

    try:
        while True:
            text = await ws.receive_text()
            msg = json.loads(text)
            # Worker sends alarm_triggered — forward to admins
            if msg.get("type") == "alarm_triggered":
                await manager.broadcast_admins(msg)
    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception:
        manager.disconnect(ws)
```

- [ ] **Step 2: Add broadcast to POST /api/logs**

Make `create_public_log` async and add broadcast after successful log creation:

```python
@app.post("/api/logs", response_model=LogOut)
async def create_public_log(body: LogCreate):
    confirmed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO logs (area_id, staff_id, action, confirmed_at) VALUES (?, ?, 'checked', ?)",
            (body.area_id, body.staff_id, confirmed_at),
        )
        log_id = cur.lastrowid
        row = db.execute(
            """SELECT l.id, l.area_id, a.name AS area_name,
                      l.staff_id, s.name AS staff_name,
                      l.action, l.alarm_time, l.confirmed_at
               FROM logs l JOIN areas a ON a.id = l.area_id
               LEFT JOIN staff s ON s.id = l.staff_id WHERE l.id = ?""",
            (log_id,),
        ).fetchone()
    result = dict(row)
    # Broadcast to admin dashboards
    await manager.broadcast_admins({
        "type": "alarm_confirmed",
        "area_id": result["area_id"],
        "area_name": result["area_name"],
        "staff_id": result["staff_id"],
        "staff_name": result["staff_name"],
        "confirmed_at": result["confirmed_at"],
    })
    return result
```

- [ ] **Step 3: Add broadcast to admin CRUD endpoints**

Make each admin create/update/delete endpoint async. After successful DB operation, broadcast `config_changed` to workers.

Add this helper:

```python
async def notify_config_change(change_type: str):
    await manager.broadcast_workers({"type": "config_changed", "change": change_type})
```

Then add `await notify_config_change("areas")` after each area CRUD, `"staff"` after staff CRUD, `"shifts"` after shift CRUD. Make each endpoint `async def` instead of `def`.

Example for `admin_create_area`:
```python
@app.post("/api/admin/{token}/areas", response_model=AreaOut, status_code=201)
async def admin_create_area(token: str, body: AreaCreate):
    verify_token(token)
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO areas (name, interval_min, delay_threshold_min) VALUES (?, ?, ?)",
            (body.name, body.interval_min, body.delay_threshold_min),
        )
        area_id = cur.lastrowid
    await notify_config_change("areas")
    return {"id": area_id, "name": body.name, "interval_min": body.interval_min, "delay_threshold_min": body.delay_threshold_min}
```

Apply the same pattern to: `admin_update_area`, `admin_delete_area`, `admin_create_staff`, `admin_delete_staff`, `admin_create_shift`, `admin_delete_shift`.

- [ ] **Step 4: Test WebSocket**

```bash
DB_PATH=./data/bex.db ADMIN_TOKEN=test123 python3 -m uvicorn main:app --port 8765 &
sleep 2
# Test WebSocket connects (use python):
python3 -c "
import asyncio, websockets, json
async def test():
    async with websockets.connect('ws://localhost:8765/ws') as ws:
        await ws.send(json.dumps({'role':'admin'}))
        print('Connected as admin')
        # In another terminal, POST a log — should receive alarm_confirmed
asyncio.run(test())
" &
sleep 1
curl -s -X POST http://localhost:8765/api/admin/test123/areas -H "Content-Type: application/json" -d '{"name":"Test","interval_min":30}' > /dev/null
curl -s -X POST http://localhost:8765/api/admin/test123/staff -H "Content-Type: application/json" -d '{"name":"Test Person"}' > /dev/null
curl -s -X POST http://localhost:8765/api/logs -H "Content-Type: application/json" -d '{"area_id":1,"staff_id":1}'
kill %1 %2 2>/dev/null; rm -rf ./data
```

- [ ] **Step 5: Commit**

```bash
git add main.py
git commit -m "feat: WebSocket endpoint with broadcast to admin/worker groups"
```

---

## Chunk 2: Frontend WebSocket Entegrasyonu

### Task 4: Worker view — WebSocket connection and config_changed handler

**Files:**
- Modify: `static/index.html`

- [ ] **Step 1: Add WebSocket connection logic to index.html**

Add this after the `loadState()` function, before the INIT section:

```javascript
// --- WEBSOCKET ---
let ws = null;
let wsRetryDelay = 1000;

function connectWS() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(proto + '//' + location.host + '/ws');

    ws.onopen = () => {
        ws.send(JSON.stringify({role: 'worker'}));
        wsRetryDelay = 1000;
    };

    ws.onmessage = (e) => {
        try {
            const msg = JSON.parse(e.data);
            if (msg.type === 'config_changed') {
                loadState(); // Reload everything from API
            }
        } catch(err) {}
    };

    ws.onclose = () => {
        setTimeout(connectWS, Math.min(wsRetryDelay, 30000));
        wsRetryDelay *= 2;
    };

    ws.onerror = () => { ws.close(); };
}
```

- [ ] **Step 2: Modify confirmAlarm to also send alarm_triggered via WebSocket**

In the `queueAlarm` function (where alarm is triggered), add WebSocket notification:

```javascript
function queueAlarm(areaId){
    const assignedStaffId = pickNext(areaId);
    alarmQueue.push({areaId, assignedStaffId});
    playAlarm();
    // Notify admin via WebSocket
    if (ws && ws.readyState === WebSocket.OPEN) {
        const area = state.areas.find(a => a.id === areaId);
        const staff = assignedStaffId ? state.staff.find(s => s.id === assignedStaffId) : null;
        ws.send(JSON.stringify({
            type: 'alarm_triggered',
            area_id: areaId,
            area_name: area ? area.name : '?',
            staff_id: assignedStaffId,
            staff_name: staff ? staff.name : null,
            alarm_time: new Date().toISOString()
        }));
    }
    if(!alarmOpen) showNextAlarm();
}
```

- [ ] **Step 3: Update INIT section**

```javascript
// --- INIT ---
loadState();
connectWS();
setInterval(loadState, 300000); // Fallback polling
```

- [ ] **Step 4: Commit**

```bash
git add static/index.html
git commit -m "feat: worker WebSocket — config_changed handler, alarm_triggered sender"
```

---

### Task 5: Admin panel — Canli Izleme sekmesi and WebSocket

**Files:**
- Modify: `static/admin.html`

- [ ] **Step 1: Add "Canli Izleme" tab button to header**

Add a new tab button in the header nav: `<button class="tab-btn" data-tab="live">Canlı İzleme</button>`

- [ ] **Step 2: Add Canli Izleme pane HTML**

Add this pane inside `<main>`:

```html
<div id="pane-live" class="tab-pane">
    <div class="panel-top">
        <div>
            <div class="panel-title">Canlı İzleme</div>
            <div class="today-info" id="live-today-info"></div>
        </div>
        <div id="live-connection-badge" class="badge badge-off">Bağlanıyor...</div>
    </div>
    <div class="timer-grid" id="live-grid"></div>
</div>
```

- [ ] **Step 3: Add CSS for live monitoring cards**

```css
.live-card{background:var(--card);border-radius:14px;border:2px solid var(--border);padding:16px;text-align:center;transition:all .3s}
.live-card.status-ok{border-color:var(--success);background:var(--success-bg)}
.live-card.status-alarm{border-color:var(--amber);background:var(--amber-pale);animation:borderPulse 1s ease-in-out infinite}
.live-card.status-late{border-color:var(--danger);background:var(--danger-bg);animation:borderPulse .5s ease-in-out infinite}
.live-card.status-idle{border-color:var(--border)}
.live-card-name{font-size:14px;font-weight:700;margin-bottom:8px}
.live-card-status{font-size:12px;color:var(--muted);margin-bottom:4px}
.live-card-detail{font-size:11px;color:var(--muted)}
.live-card-time{font-size:22px;font-weight:800;margin:8px 0}
```

- [ ] **Step 4: Add live monitoring JS logic**

Track active alarms and last check times:

```javascript
// Live monitoring state
let liveAlarms = {}; // {areaId: {staff_name, alarm_time (Date)}}
let lastChecks = {}; // {areaId: {staff_name, confirmed_at (Date)}}

function renderLiveGrid() {
    const grid = document.getElementById('live-grid');
    if (!grid) return;
    document.getElementById('live-today-info').textContent = DAYS_FULL[todayDayIndex()];

    if (state.areas.length === 0) {
        grid.innerHTML = '<div style="grid-column:1/-1;padding:32px;text-align:center;color:var(--muted)">Henüz alan eklenmedi.</div>';
        return;
    }

    const now = Date.now();
    grid.innerHTML = state.areas.map(a => {
        const alarm = liveAlarms[a.id];
        const check = lastChecks[a.id];
        const threshold = (a.delay_threshold_min || 5) * 60 * 1000;

        let statusClass = 'status-idle';
        let statusText = 'Bekleniyor';
        let detail = '';
        let timeDisplay = '';

        if (alarm) {
            const elapsed = now - alarm.alarm_time.getTime();
            if (elapsed > threshold) {
                statusClass = 'status-late';
                const delaySec = Math.round(elapsed / 1000);
                timeDisplay = delaySec < 60 ? delaySec + 'sn' : Math.round(delaySec/60) + 'dk';
                statusText = 'GECİKME!';
                detail = alarm.staff_name ? alarm.staff_name + ' atandı' : 'Kimse atanmadı';
            } else {
                statusClass = 'status-alarm';
                const remainSec = Math.round((threshold - elapsed) / 1000);
                timeDisplay = remainSec < 60 ? remainSec + 'sn' : Math.round(remainSec/60) + 'dk';
                statusText = 'Alarm aktif';
                detail = alarm.staff_name ? alarm.staff_name + ' kontrol edecek' : '';
            }
        } else if (check) {
            statusClass = 'status-ok';
            const checkTime = check.confirmed_at;
            timeDisplay = checkTime.toLocaleTimeString('tr-TR', {hour:'2-digit', minute:'2-digit'});
            statusText = 'Kontrol yapıldı';
            detail = check.staff_name || '';
        }

        const icon = ICONS[state.areas.indexOf(a) % ICONS.length];
        return `<div class="live-card ${statusClass}">
            <div style="font-size:24px;margin-bottom:4px">${icon}</div>
            <div class="live-card-name">${a.name}</div>
            <div class="live-card-time">${timeDisplay || '--'}</div>
            <div class="live-card-status">${statusText}</div>
            <div class="live-card-detail">${detail}</div>
        </div>`;
    }).join('');
}

// Update live grid every second (for elapsed time counters)
setInterval(() => {
    if (activeTab === 'live') renderLiveGrid();
}, 1000);
```

- [ ] **Step 5: Add WebSocket connection for admin**

```javascript
let ws = null;
let wsRetryDelay = 1000;

function connectWS() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(proto + '//' + location.host + '/ws');

    ws.onopen = () => {
        ws.send(JSON.stringify({role: 'admin'}));
        wsRetryDelay = 1000;
        const badge = document.getElementById('live-connection-badge');
        if (badge) { badge.textContent = 'Bağlı'; badge.className = 'badge badge-ok'; }
    };

    ws.onmessage = (e) => {
        try {
            const msg = JSON.parse(e.data);
            if (msg.type === 'alarm_triggered') {
                liveAlarms[msg.area_id] = {
                    staff_name: msg.staff_name,
                    alarm_time: new Date(msg.alarm_time)
                };
                if (activeTab === 'live') renderLiveGrid();
            }
            if (msg.type === 'alarm_confirmed') {
                delete liveAlarms[msg.area_id];
                lastChecks[msg.area_id] = {
                    staff_name: msg.staff_name,
                    confirmed_at: new Date(msg.confirmed_at + (msg.confirmed_at.includes('Z') ? '' : 'Z'))
                };
                if (activeTab === 'live') renderLiveGrid();
            }
        } catch(err) {}
    };

    ws.onclose = () => {
        const badge = document.getElementById('live-connection-badge');
        if (badge) { badge.textContent = 'Bağlantı kesildi'; badge.className = 'badge badge-warn'; }
        setTimeout(connectWS, Math.min(wsRetryDelay, 30000));
        wsRetryDelay *= 2;
    };

    ws.onerror = () => { ws.close(); };
}
```

- [ ] **Step 6: Add delay_threshold_min to Alanlar tab**

In the areas table, add a column for gecikme esigi:

Table header: `<th>Alan Adı</th><th>Kontrol Sıklığı</th><th>Gecikme Eşiği</th><th></th>`

In each area row, add an editable input:
```html
<td><div class="interval-edit">
    <input type="number" min="1" max="60" value="${a.delay_threshold_min}" id="idel-${a.id}" style="width:50px">
    <span style="font-size:12px;color:var(--muted)">dk</span>
</div></td>
```

Update `saveInterval` to also send `delay_threshold_min`:
```javascript
async function saveInterval(areaId) {
    const val = parseInt(document.getElementById('imin-' + areaId).value);
    const del = parseInt(document.getElementById('idel-' + areaId).value) || 5;
    if (!val || val < 1) { alert('Gecerli bir deger giriniz'); return; }
    await api(`/areas/${areaId}`, { method: 'PATCH', body: JSON.stringify({interval_min: val, delay_threshold_min: del}) });
    // ... rest of function
}
```

- [ ] **Step 7: Update tab switching to include 'live' tab**

Make sure the tab click handler renders `renderLiveGrid()` when `tab === 'live'`.

- [ ] **Step 8: Initialize WebSocket on page load**

Add to the init section:
```javascript
loadState().then(() => {
    connectWS();
});
```

- [ ] **Step 9: Commit**

```bash
git add static/admin.html
git commit -m "feat: admin live monitoring dashboard with WebSocket"
```

---

## Chunk 3: Deploy and Verify

### Task 6: Deploy to production and end-to-end test

**Files:**
- No file changes (just deploy and verify)

- [ ] **Step 1: Push to GitHub**

```bash
git push origin master
```

- [ ] **Step 2: Trigger Coolify deploy**

```bash
curl -s -H "Authorization: Bearer <COOLIFY_TOKEN>" "https://deploy.saviordigital.com/api/v1/deploy?uuid=ow82ix72ykf0n5aa5pcimktj&force=true"
```

- [ ] **Step 3: Wait for deploy and verify**

```bash
# Check deploy status
curl -s -H "Authorization: Bearer <COOLIFY_TOKEN>" "https://deploy.saviordigital.com/api/v1/deployments/<uuid>"

# Test API returns delay_threshold_min
curl -s https://bex.saviordigital.com/api/areas
# Should include "delay_threshold_min":5 for each area

# Test WebSocket endpoint exists
# (WebSocket upgrade test)
```

- [ ] **Step 4: End-to-end test**

1. Open worker view on one device (iPad)
2. Open admin panel on another device — go to "Canlı İzleme" tab
3. Wait for or trigger alarm on worker view
4. Admin should see area card turn orange immediately
5. If worker doesn't confirm within threshold → card turns red
6. Worker confirms alarm → admin card turns green with check time
7. Admin changes an area interval → worker view refreshes automatically

- [ ] **Step 5: Update existing areas with delay_threshold_min**

Migration already sets default to 5. Verify:
```bash
curl -s https://bex.saviordigital.com/api/areas
```

All existing areas should have `delay_threshold_min: 5`.
