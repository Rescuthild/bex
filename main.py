import os
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from database import get_db, init_db, migrate_db
from models import (
    AreaCreate, AreaOut, AreaUpdate,
    LogCreate, LogOut,
    ShiftCreate, ShiftOut,
    StaffCreate, StaffOut,
)

app = FastAPI(title="BEX Coffee")

ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "dev-token-change-me")


def verify_token(token: str):
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=404, detail="Not found")


@app.on_event("startup")
def on_startup():
    init_db()
    migrate_db()


# ═══════════════════════════════════════════════════════
# Page routes
# ═══════════════════════════════════════════════════════

@app.get("/", include_in_schema=False)
def index_page():
    return FileResponse("static/index.html")


@app.get("/admin/{token}", include_in_schema=False)
def admin_page(token: str):
    verify_token(token)
    return FileResponse("static/admin.html")


# ═══════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════

@app.get("/api/areas", response_model=list[AreaOut])
def list_areas():
    with get_db() as db:
        rows = db.execute("SELECT id, name, interval_min, delay_threshold_min FROM areas ORDER BY id").fetchall()
    return [dict(r) for r in rows]


@app.get("/api/staff/active", response_model=list[StaffOut])
def active_staff():
    """Return staff currently on shift (based on JS day_of_week and current time)."""
    now = datetime.now()
    # Convert Python weekday (0=Mon) to JS day (0=Sun)
    js_day = (now.weekday() + 1) % 7
    current_time = now.strftime("%H:%M")
    with get_db() as db:
        rows = db.execute(
            """
            SELECT DISTINCT s.id, s.name
            FROM staff s
            JOIN shifts sh ON sh.staff_id = s.id
            WHERE sh.day_of_week = ?
              AND sh.shift_start <= ?
              AND sh.shift_end > ?
            ORDER BY s.name
            """,
            (js_day, current_time, current_time),
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/shifts/today", response_model=list[ShiftOut])
def shifts_today():
    """Return today's shift schedule."""
    now = datetime.now()
    js_day = (now.weekday() + 1) % 7
    with get_db() as db:
        rows = db.execute(
            """
            SELECT sh.id, sh.staff_id, s.name AS staff_name,
                   sh.day_of_week, sh.shift_start, sh.shift_end
            FROM shifts sh
            JOIN staff s ON s.id = sh.staff_id
            WHERE sh.day_of_week = ?
            ORDER BY sh.shift_start
            """,
            (js_day,),
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/logs", response_model=LogOut)
def create_public_log(body: LogCreate):
    """Create a 'checked' log entry from the public panel."""
    confirmed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as db:
        cur = db.execute(
            """
            INSERT INTO logs (area_id, staff_id, action, confirmed_at)
            VALUES (?, ?, 'checked', ?)
            """,
            (body.area_id, body.staff_id, confirmed_at),
        )
        log_id = cur.lastrowid
        row = db.execute(
            """
            SELECT l.id, l.area_id, a.name AS area_name,
                   l.staff_id, s.name AS staff_name,
                   l.action, l.alarm_time, l.confirmed_at
            FROM logs l
            JOIN areas a ON a.id = l.area_id
            LEFT JOIN staff s ON s.id = l.staff_id
            WHERE l.id = ?
            """,
            (log_id,),
        ).fetchone()
    return dict(row)


# ═══════════════════════════════════════════════════════
# Admin API — Areas
# ═══════════════════════════════════════════════════════

@app.get("/api/admin/{token}/areas", response_model=list[AreaOut])
def admin_list_areas(token: str):
    verify_token(token)
    with get_db() as db:
        rows = db.execute("SELECT id, name, interval_min, delay_threshold_min FROM areas ORDER BY id").fetchall()
    return [dict(r) for r in rows]


@app.post("/api/admin/{token}/areas", response_model=AreaOut, status_code=201)
def admin_create_area(token: str, body: AreaCreate):
    verify_token(token)
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO areas (name, interval_min, delay_threshold_min) VALUES (?, ?, ?)",
            (body.name, body.interval_min, body.delay_threshold_min),
        )
        area_id = cur.lastrowid
    return {"id": area_id, "name": body.name, "interval_min": body.interval_min, "delay_threshold_min": body.delay_threshold_min}


@app.patch("/api/admin/{token}/areas/{area_id}", response_model=AreaOut)
def admin_update_area(token: str, area_id: int, body: AreaUpdate):
    verify_token(token)
    with get_db() as db:
        existing = db.execute("SELECT id, name, interval_min, delay_threshold_min FROM areas WHERE id = ?", (area_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Area not found")
        new_name = body.name if body.name is not None else existing["name"]
        new_interval = body.interval_min if body.interval_min is not None else existing["interval_min"]
        new_delay = body.delay_threshold_min if body.delay_threshold_min is not None else existing["delay_threshold_min"]
        db.execute(
            "UPDATE areas SET name = ?, interval_min = ?, delay_threshold_min = ? WHERE id = ?",
            (new_name, new_interval, new_delay, area_id),
        )
    return {"id": area_id, "name": new_name, "interval_min": new_interval, "delay_threshold_min": new_delay}


@app.delete("/api/admin/{token}/areas/{area_id}", status_code=204)
def admin_delete_area(token: str, area_id: int):
    verify_token(token)
    with get_db() as db:
        db.execute("DELETE FROM areas WHERE id = ?", (area_id,))
    return None


# ═══════════════════════════════════════════════════════
# Admin API — Staff
# ═══════════════════════════════════════════════════════

@app.get("/api/admin/{token}/staff", response_model=list[StaffOut])
def admin_list_staff(token: str):
    verify_token(token)
    with get_db() as db:
        rows = db.execute("SELECT id, name FROM staff ORDER BY id").fetchall()
    return [dict(r) for r in rows]


@app.post("/api/admin/{token}/staff", response_model=StaffOut, status_code=201)
def admin_create_staff(token: str, body: StaffCreate):
    verify_token(token)
    with get_db() as db:
        cur = db.execute("INSERT INTO staff (name) VALUES (?)", (body.name,))
        staff_id = cur.lastrowid
    return {"id": staff_id, "name": body.name}


@app.delete("/api/admin/{token}/staff/{staff_id}", status_code=204)
def admin_delete_staff(token: str, staff_id: int):
    verify_token(token)
    with get_db() as db:
        db.execute("DELETE FROM staff WHERE id = ?", (staff_id,))
    return None


# ═══════════════════════════════════════════════════════
# Admin API — Shifts
# ═══════════════════════════════════════════════════════

@app.get("/api/admin/{token}/shifts", response_model=list[ShiftOut])
def admin_list_shifts(token: str):
    verify_token(token)
    with get_db() as db:
        rows = db.execute(
            """
            SELECT sh.id, sh.staff_id, s.name AS staff_name,
                   sh.day_of_week, sh.shift_start, sh.shift_end
            FROM shifts sh
            JOIN staff s ON s.id = sh.staff_id
            ORDER BY sh.day_of_week, sh.shift_start
            """
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/admin/{token}/shifts", response_model=ShiftOut, status_code=201)
def admin_create_shift(token: str, body: ShiftCreate):
    verify_token(token)
    with get_db() as db:
        # Verify staff exists
        staff = db.execute("SELECT id, name FROM staff WHERE id = ?", (body.staff_id,)).fetchone()
        if not staff:
            raise HTTPException(status_code=404, detail="Staff not found")
        cur = db.execute(
            "INSERT INTO shifts (staff_id, day_of_week, shift_start, shift_end) VALUES (?, ?, ?, ?)",
            (body.staff_id, body.day_of_week, body.shift_start, body.shift_end),
        )
        shift_id = cur.lastrowid
    return {
        "id": shift_id,
        "staff_id": body.staff_id,
        "staff_name": staff["name"],
        "day_of_week": body.day_of_week,
        "shift_start": body.shift_start,
        "shift_end": body.shift_end,
    }


@app.delete("/api/admin/{token}/shifts/{shift_id}", status_code=204)
def admin_delete_shift(token: str, shift_id: int):
    verify_token(token)
    with get_db() as db:
        db.execute("DELETE FROM shifts WHERE id = ?", (shift_id,))
    return None


# ═══════════════════════════════════════════════════════
# Admin API — Logs
# ═══════════════════════════════════════════════════════

@app.get("/api/admin/{token}/logs", response_model=list[LogOut])
def admin_list_logs(
    token: str,
    date: Optional[str] = Query(None, description="Filter by date YYYY-MM-DD"),
    area_id: Optional[int] = Query(None, description="Filter by area ID"),
):
    verify_token(token)
    query = """
        SELECT l.id, l.area_id, a.name AS area_name,
               l.staff_id, s.name AS staff_name,
               l.action, l.alarm_time, l.confirmed_at
        FROM logs l
        JOIN areas a ON a.id = l.area_id
        LEFT JOIN staff s ON s.id = l.staff_id
        WHERE 1=1
    """
    params: list = []
    if date:
        query += " AND DATE(l.alarm_time) = ?"
        params.append(date)
    if area_id is not None:
        query += " AND l.area_id = ?"
        params.append(area_id)
    query += " ORDER BY l.alarm_time DESC"
    with get_db() as db:
        rows = db.execute(query, params).fetchall()
    return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════
# Static files (mounted last so it doesn't shadow routes)
# ═══════════════════════════════════════════════════════

app.mount("/static", StaticFiles(directory="static"), name="static")
