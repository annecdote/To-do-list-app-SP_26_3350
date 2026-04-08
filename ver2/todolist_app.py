
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse, urlencode, quote_plus
from pathlib import Path
import sqlite3
import datetime
import html

APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / "data"
DB_FILE = DATA_DIR / "taskflow.db"

DEFAULT_PROJECTS = ["Work", "Personal", "Groceries"]
PRIORITIES = ["Low", "Medium", "High"]
LABELS = ["", "Today", "Next Week"]


def now_iso():
    return datetime.datetime.now().replace(microsecond=0).isoformat()


def connect_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect_db() as conn:
        conn.executescript(
            '''
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                project TEXT NOT NULL,
                label TEXT NOT NULL DEFAULT '',
                priority TEXT NOT NULL DEFAULT 'Medium',
                due_date TEXT,
                completed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                position INTEGER NOT NULL DEFAULT 0
            );
            '''
        )

        existing_projects = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        if existing_projects == 0:
            conn.executemany(
                "INSERT INTO projects (name, created_at) VALUES (?, ?)",
                [(name, now_iso()) for name in DEFAULT_PROJECTS],
            )

        existing_tasks = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        if existing_tasks == 0:
            ts = now_iso()
            seed = [
                ("Finish project proposal for Client A", "", "Work", "", "High", None, 0, ts, 1),
                ("Buy milk and bread", "", "Groceries", "Today", "Medium", None, 0, ts, 2),
                ("Schedule dentist appointment", "", "Personal", "", "Medium", None, 0, ts, 3),
                ("Review design assets", "", "Work", "", "Low", None, 0, ts, 4),
                ("Call Mom", "", "Personal", "", "Medium", None, 0, ts, 5),
                ("Update website blog post", "", "Work", "Next Week", "Low", None, 0, ts, 6),
            ]
            conn.executemany(
                '''
                INSERT INTO tasks
                (task, notes, project, label, priority, due_date, completed, created_at, position)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                seed,
            )
        conn.commit()


def normalize_positions(conn):
    rows = conn.execute("SELECT id FROM tasks ORDER BY position, id").fetchall()
    for index, row in enumerate(rows, start=1):
        conn.execute("UPDATE tasks SET position = ? WHERE id = ?", (index, row["id"]))
    conn.commit()


def fetch_projects(conn):
    return conn.execute(
        '''
        SELECT p.name,
               COUNT(t.id) AS total_count,
               SUM(CASE WHEN t.completed = 0 THEN 1 ELSE 0 END) AS open_count
        FROM projects p
        LEFT JOIN tasks t ON t.project = p.name
        GROUP BY p.name
        ORDER BY p.name COLLATE NOCASE
        '''
    ).fetchall()


def get_task(conn, task_id):
    return conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()


def priority_rank(value):
    return {"High": 0, "Medium": 1, "Low": 2}.get(value, 3)


def label_rank(value):
    return {"Today": 0, "Next Week": 1, "": 2}.get(value, 3)


def parse_due_date(raw):
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return datetime.date.fromisoformat(raw).isoformat()
    except ValueError:
        return None


def task_sort_key(task, sort_by):
    if sort_by == "date":
        return (task["created_at"], task["position"])
    if sort_by == "priority":
        return (priority_rank(task["priority"]), task["position"])
    if sort_by == "label":
        return (label_rank(task["label"]), task["position"])
    if sort_by == "due":
        no_due = 1 if not task["due_date"] else 0
        return (no_due, task["due_date"] or "9999-12-31", task["position"])
    return (task["position"],)


def fetch_tasks(conn, project_filter, sort_by, search_term, show_filter):
    tasks = conn.execute("SELECT * FROM tasks").fetchall()
    if project_filter and project_filter != "Inbox":
        tasks = [row for row in tasks if row["project"] == project_filter]

    if search_term:
        needle = search_term.casefold()
        tasks = [row for row in tasks if needle in row["task"].casefold() or needle in (row["notes"] or "").casefold()]

    if show_filter == "active":
        tasks = [row for row in tasks if not row["completed"]]
    elif show_filter == "completed":
        tasks = [row for row in tasks if row["completed"]]

    reverse = sort_by == "date"
    tasks = sorted(tasks, key=lambda row: task_sort_key(row, sort_by), reverse=reverse)

    if show_filter == "all":
        incomplete = [row for row in tasks if not row["completed"]]
        complete = [row for row in tasks if row["completed"]]
        return incomplete + complete
    return tasks


def build_query(project_filter="Inbox", sort_by="manual", editing_id=None, search_term="", show_filter="all"):
    params = {}
    if project_filter and project_filter != "Inbox":
        params["project"] = project_filter
    if sort_by and sort_by != "manual":
        params["sort"] = sort_by
    if editing_id is not None:
        params["edit"] = str(editing_id)
    if search_term:
        params["q"] = search_term
    if show_filter and show_filter != "all":
        params["show"] = show_filter
    q = urlencode(params)
    return f"?{q}" if q else ""


def dashboard_stats(conn):
    total = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    open_count = conn.execute("SELECT COUNT(*) FROM tasks WHERE completed = 0").fetchone()[0]
    completed = conn.execute("SELECT COUNT(*) FROM tasks WHERE completed = 1").fetchone()[0]
    due_today = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE due_date = ? AND completed = 0",
        (datetime.date.today().isoformat(),),
    ).fetchone()[0]
    return {"total": total, "open": open_count, "completed": completed, "due_today": due_today}


def truncate_project_name(name, limit=10):
    return name if len(name) <= limit else name[:10] + "...."


def project_delete_allowed(conn, project_name):
    if project_name in set(DEFAULT_PROJECTS):
        return False
    count = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    return count > 1


def icon_svg(kind):
    if kind == "inbox":
        path = "M19,3H4.99C3.88,3 3,3.89 3,5V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19V5A2,2 0 0,0 19,3M19,19H5V5H19V19M17,11H15V13H9V11H7V15H17V11Z"
    else:
        path = "M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M10,17L5,12L6.41,10.59L10,14.17L17.59,6.58L19,8L10,17Z"
    return f"<svg viewBox='0 0 24 24' aria-hidden='true' class='nav-svg'><path fill='currentColor' d='{path}'/></svg>"


class TodoHandler(BaseHTTPRequestHandler):
    def redirect_home(self, project_filter="Inbox", sort_by="manual", search_term="", show_filter="all"):
        self.send_response(303)
        self.send_header("Location", "/" + build_query(project_filter, sort_by, None, search_term, show_filter))
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        project_filter = query.get("project", ["Inbox"])[0]
        sort_by = query.get("sort", ["manual"])[0]
        search_term = query.get("q", [""])[0].strip()
        show_filter = query.get("show", ["all"])[0]
        editing_id = int(query.get("edit", ["0"])[0]) if query.get("edit") else None

        with connect_db() as conn:
            if parsed.path == "/delete":
                tid = int(query.get("id", [0])[0])
                conn.execute("DELETE FROM tasks WHERE id = ?", (tid,))
                normalize_positions(conn)
                self.redirect_home(project_filter, sort_by, search_term, show_filter)
                return

            if parsed.path == "/toggle":
                tid = int(query.get("id", [0])[0])
                task = get_task(conn, tid)
                if task:
                    conn.execute("UPDATE tasks SET completed = ? WHERE id = ?", (0 if task["completed"] else 1, tid))
                    conn.commit()
                self.redirect_home(project_filter, sort_by, search_term, show_filter)
                return

            if parsed.path == "/move":
                tid = int(query.get("id", [0])[0])
                direction = query.get("dir", [""])[0]
                normalize_positions(conn)
                ordered = conn.execute("SELECT id, position FROM tasks ORDER BY position, id").fetchall()
                ids = [row["id"] for row in ordered]
                if tid in ids:
                    idx = ids.index(tid)
                    if direction == "up" and idx > 0:
                        first = ordered[idx]
                        second = ordered[idx - 1]
                        conn.execute("UPDATE tasks SET position = ? WHERE id = ?", (second["position"], first["id"]))
                        conn.execute("UPDATE tasks SET position = ? WHERE id = ?", (first["position"], second["id"]))
                    elif direction == "down" and idx < len(ordered) - 1:
                        first = ordered[idx]
                        second = ordered[idx + 1]
                        conn.execute("UPDATE tasks SET position = ? WHERE id = ?", (second["position"], first["id"]))
                        conn.execute("UPDATE tasks SET position = ? WHERE id = ?", (first["position"], second["id"]))
                    conn.commit()
                    normalize_positions(conn)
                self.redirect_home(project_filter, sort_by, search_term, show_filter)
                return

            if parsed.path == "/clear_completed":
                conn.execute("DELETE FROM tasks WHERE completed = 1")
                conn.commit()
                normalize_positions(conn)
                self.redirect_home(project_filter, sort_by, search_term, show_filter)
                return

            if parsed.path == "/delete_project":
                project_name = query.get("name", [""])[0].strip()
                if project_name and project_delete_allowed(conn, project_name):
                    fallback = conn.execute(
                        "SELECT name FROM projects WHERE name != ? ORDER BY created_at, id LIMIT 1",
                        (project_name,),
                    ).fetchone()
                    fallback_name = fallback["name"] if fallback else "Inbox"
                    conn.execute("UPDATE tasks SET project = ? WHERE project = ?", (fallback_name, project_name))
                    conn.execute("DELETE FROM projects WHERE name = ?", (project_name,))
                    conn.commit()
                    normalize_positions(conn)
                    next_project = fallback_name if project_filter == project_name else project_filter
                    self.redirect_home(next_project, sort_by, search_term, show_filter)
                    return
                self.redirect_home(project_filter, sort_by, search_term, show_filter)
                return

            projects = fetch_projects(conn)
            active_tasks = fetch_tasks(conn, project_filter, sort_by, search_term, show_filter)
            editing_task = get_task(conn, editing_id) if editing_id else None
            stats = dashboard_stats(conn)

            task_cards = []
            for t in active_tasks:
                is_editing = editing_task and editing_task["id"] == t["id"]
                due_badge = f"<span class='task-tag due'>Due {html.escape(t['due_date'])}</span>" if t["due_date"] else ""
                notes_html = f"<div class='task-notes'>{html.escape(t['notes'])}</div>" if t["notes"] and not is_editing else ""

                if is_editing:
                    task_cards.append(f'''
                    <div class="task-card editing">
                        <form method="POST" action="/update{build_query(project_filter, sort_by, None, search_term, show_filter)}" class="edit-form">
                            <input type="hidden" name="id" value="{t["id"]}">
                            <input class="edit-task-input" name="task" value="{html.escape(t["task"])}" required>
                            <input name="notes" value="{html.escape(t["notes"] or "")}" placeholder="Notes (optional)">
                            <select name="project">
                                {"".join([f"<option value='{html.escape(row['name'])}' {'selected' if row['name'] == t['project'] else ''}>{html.escape(row['name'])}</option>" for row in projects])}
                            </select>
                            <select name="label">
                                <option value="" {'selected' if t["label"] == '' else ''}>No Label</option>
                                <option value="Today" {'selected' if t["label"] == 'Today' else ''}>Today</option>
                                <option value="Next Week" {'selected' if t["label"] == 'Next Week' else ''}>Next Week</option>
                            </select>
                            <select name="priority">
                                {"".join([f"<option value='{p}' {'selected' if p == t['priority'] else ''}>{p}</option>" for p in PRIORITIES])}
                            </select>
                            <input type="date" name="due_date" value="{html.escape(t["due_date"] or "")}">
                            <div class="edit-actions">
                                <button class="mini-btn primary" type="submit">Save</button>
                                <a class="mini-btn ghost" href="/{build_query(project_filter, sort_by, None, search_term, show_filter)}">Cancel</a>
                            </div>
                        </form>
                    </div>
                    ''')
                    continue

                label_html = f"<span class='task-tag {t['label'].lower().replace(' ', '-')}'>{html.escape(t['label'])}</span>" if t["label"] else ""
                priority_html = f"<span class='priority-badge {t['priority'].lower()}'>{html.escape(t['priority'])}</span>"
                checked = "checked-box" if t["completed"] else ""
                completed_class = "completed" if t["completed"] else ""

                task_cards.append(f'''
                <div class="task-card">
                    <div class="task-left">
                        <a class="checkbox {checked}" href="/toggle?id={t["id"]}&project={quote_plus(project_filter)}&sort={quote_plus(sort_by)}&q={quote_plus(search_term)}&show={quote_plus(show_filter)}" title="Toggle complete"></a>
                        <div class="task-main">
                            <div class="task-text {completed_class}">{html.escape(t["task"])}</div>
                            {notes_html}
                            <div class="task-meta">
                                <span class="meta-chip">{html.escape(t["project"])}</span>
                                {priority_html}
                                {label_html}
                                {due_badge}
                            </div>
                        </div>
                    </div>
                    <div class="task-actions">
                        <a class="icon-btn" href="/{build_query(project_filter, sort_by, t['id'], search_term, show_filter)}" title="Edit">✎</a>
                        <a class="icon-btn" href="/delete?id={t["id"]}&project={quote_plus(project_filter)}&sort={quote_plus(sort_by)}&q={quote_plus(search_term)}&show={quote_plus(show_filter)}" title="Delete">🗑</a>
                        <a class="icon-btn" href="/move?id={t["id"]}&dir=up&project={quote_plus(project_filter)}&sort={quote_plus(sort_by)}&q={quote_plus(search_term)}&show={quote_plus(show_filter)}" title="Move up">⌃</a>
                        <a class="icon-btn" href="/move?id={t["id"]}&dir=down&project={quote_plus(project_filter)}&sort={quote_plus(sort_by)}&q={quote_plus(search_term)}&show={quote_plus(show_filter)}" title="Move down">⌄</a>
                    </div>
                </div>
                ''')

            tasks_html = "\n".join(task_cards) if task_cards else '<div class="empty-state">No tasks in this view.</div>'

            project_links = []
            for row in projects:
                p = row["name"]
                active = "sub-item active-sub" if p == project_filter else "sub-item"
                delete_control = ""
                if project_delete_allowed(conn, p):
                    delete_control = (
                        f"<a class='project-delete' title='Delete project' "
                        f"href='/delete_project?name={quote_plus(p)}&project={quote_plus(project_filter)}&sort={quote_plus(sort_by)}&q={quote_plus(search_term)}&show={quote_plus(show_filter)}'>×</a>"
                    )
                display_name = html.escape(truncate_project_name(p))
                project_links.append(
                    f"<div class='project-row'><a class='{active}' href='/{build_query(p, sort_by, None, search_term, show_filter)}' title='{html.escape(p)}'><span class='project-name'>{display_name}</span><span>{row['open_count'] or 0}</span></a>{delete_control}</div>"
                )

            sort_label = {"manual": "Manual", "date": "Date", "priority": "Priority", "label": "Label", "due": "Due Date"}.get(sort_by, "Manual")

            html_page = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TaskFlow</title>
<style>
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; background: #edf1f6; color: #1d2433; }}
a {{ text-decoration: none; }}
.window {{ max-width: 1280px; margin: 34px auto; background: #f8fafc; border-radius: 18px; overflow: hidden; box-shadow: 0 22px 55px rgba(0, 0, 0, 0.18); border: 1px solid rgba(255,255,255,0.6); }}
.browser-bar {{ height: 44px; background: linear-gradient(to bottom, #f7f8fb, #eceff3); display: flex; align-items: center; gap: 14px; padding: 0 14px; border-bottom: 1px solid #dfe5ec; }}
.dots {{ display: flex; gap: 8px; }}
.dot {{ width: 12px; height: 12px; border-radius: 50%; }}
.red {{ background: #ff5f57; }} .yellow {{ background: #febc2e; }} .green {{ background: #28c840; }}
.tab {{ background: white; border-radius: 10px 10px 0 0; padding: 9px 16px; font-size: 15px; color: #404856; }}
.app {{ display: flex; min-height: 780px; }}
.sidebar {{ width: 335px; background: radial-gradient(circle at 20% 10%, rgba(75, 140, 255, 0.22), transparent 24%), linear-gradient(180deg, #122844 0%, #132842 44%, #102238 100%); color: white; padding: 24px 22px 28px; }}
.brand {{ display: flex; align-items: center; gap: 14px; font-size: 24px; font-weight: 700; margin-bottom: 34px; }}
.brand-icon {{ width: 38px; height: 38px; border-radius: 10px; background: linear-gradient(135deg, #4f89ff, #6aa1ff); display: grid; place-items: center; box-shadow: 0 10px 20px rgba(0,0,0,0.2); }}
.nav-item, .sub-item {{ display: flex; align-items: center; justify-content: space-between; color: rgba(255,255,255,0.9); padding: 14px 16px; border-radius: 14px; margin-bottom: 8px; font-size: 18px; }}
.nav-item:hover, .sub-item:hover {{ background: rgba(255,255,255,0.08); }}
.nav-item.active {{ background: rgba(255,255,255,0.14); }}
.nav-label {{ display: flex; align-items: center; gap: 10px; }}
.nav-svg {{ width: 20px; height: 20px; flex-shrink: 0; }}
.section-title {{ display: flex; justify-content: space-between; align-items: center; padding: 12px 14px; margin-top: 16px; margin-bottom: 8px; font-size: 17px; color: rgba(255,255,255,0.88); }}
.project-row {{ display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }}
.sub-item {{ margin-bottom: 0; padding-left: 24px; font-size: 17px; min-width: 0; flex: 1; }}
.project-name {{ min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.project-delete {{ width: 28px; height: 28px; border-radius: 8px; display: inline-grid; place-items: center; color: rgba(255,255,255,0.75); font-size: 20px; flex-shrink: 0; }}
.project-delete:hover {{ background: rgba(255,255,255,0.10); color: white; }}
.active-sub {{ background: rgba(255,255,255,0.10); }}
.outline-btn, .project-add-form button {{ display: block; width: 100%; margin-top: 12px; padding: 14px 18px; border: 1px solid rgba(255,255,255,0.28); border-radius: 14px; color: white; background: transparent; font-size: 16px; text-align: left; cursor: pointer; }}
.project-add-form input {{ width: 100%; border-radius: 14px; border: 1px solid rgba(255,255,255,0.2); background: rgba(255,255,255,0.08); color: white; padding: 12px 14px; font-size: 15px; outline: none; }}
.stats-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-top: 18px; }}
.stat-card {{ background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; padding: 12px; }}
.stat-label {{ font-size: 13px; color: rgba(255,255,255,0.75); }}
.stat-value {{ font-size: 24px; font-weight: 700; margin-top: 6px; }}
.main {{ flex: 1; background: linear-gradient(180deg, #f8fafc 0%, #eef2f7 100%); }}
.topbar {{ min-height: 74px; display: flex; align-items: center; justify-content: flex-start; gap: 20px; padding: 14px 34px 14px 48px; background: rgba(255,255,255,0.92); border-bottom: 1px solid #e4e9ef; box-shadow: 0 6px 18px rgba(18,34,56,0.05); }}
.search-form {{ display: flex; gap: 12px; align-items: center; flex: 1; }}
.search {{ width: min(520px, 100%); background: #eef2f6; border-radius: 999px; padding: 14px 20px; color: #314155; font-size: 17px; border: none; outline: none; }}
.clear-link {{ color: #6b7280; font-size: 15px; }}
.content {{ padding: 36px 48px 48px; }}
.header-row {{ display: flex; align-items: center; justify-content: space-between; gap: 14px; margin-bottom: 24px; flex-wrap: wrap; }}
.page-title {{ margin: 0; font-size: 54px; font-weight: 700; letter-spacing: -1px; color: #1c2636; }}
.header-actions {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
.add-task-btn, .secondary-btn {{ background: linear-gradient(180deg, #122a4d, #0e2340); color: white; border: none; border-radius: 14px; padding: 15px 22px; font-size: 18px; box-shadow: 0 10px 20px rgba(14,35,64,0.18); cursor: pointer; }}
.secondary-btn {{ background: #e9edf3; color: #223047; box-shadow: none; }}
.toolbar {{ display: flex; justify-content: space-between; align-items: center; gap: 14px; margin-bottom: 18px; flex-wrap: wrap; }}
.add-form {{ display: grid; grid-template-columns: 1.6fr 160px 145px 135px 150px 120px; gap: 12px; flex: 1; min-width: 760px; }}
.add-form input, .add-form select, .edit-form input, .edit-form select {{ border: 1px solid #dbe2ea; background: white; border-radius: 14px; padding: 14px 16px; font-size: 15px; outline: none; box-shadow: 0 4px 10px rgba(15, 23, 42, 0.04); }}
.filter-bar {{ display: flex; justify-content: space-between; gap: 16px; margin-bottom: 16px; align-items: center; flex-wrap: wrap; }}
.filter-pills {{ display: flex; gap: 10px; flex-wrap: wrap; }}
.pill {{ color: #5b6574; padding: 10px 12px; border-radius: 10px; background: #eef2f6; }}
.pill.active {{ background: #dfe7f2; color: #1f2937; font-weight: 600; }}
.sort-row {{ display: flex; justify-content: space-between; gap: 12px; margin-bottom: 16px; align-items: center; flex-wrap: wrap; }}
.sort-label {{ color: #525c6b; font-size: 16px; }}
.sort-pill {{ background: #e9edf3; color: #344054; padding: 8px 12px; border-radius: 10px; font-weight: 600; }}
.sort-links {{ display: flex; gap: 10px; flex-wrap: wrap; }}
.sort-link {{ color: #5b6574; padding: 8px 10px; border-radius: 10px; }}
.sort-link.active {{ background: #e7ecf2; color: #1f2937; font-weight: 600; }}
.task-list {{ display: flex; flex-direction: column; gap: 14px; }}
.task-card {{ background: white; border-radius: 16px; min-height: 78px; padding: 18px 22px; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 4px 12px rgba(15, 23, 42, 0.06); border: 1px solid #e8edf4; }}
.task-card.editing {{ padding: 16px; }}
.task-left {{ display: flex; align-items: center; gap: 16px; min-width: 0; flex: 1; }}
.task-main {{ min-width: 0; }}
.checkbox {{ width: 28px; height: 28px; border-radius: 8px; border: 2px solid #c9d2dc; background: #fff; display: inline-block; flex-shrink: 0; }}
.checked-box {{ background: linear-gradient(180deg, #5f8df9, #4f7be5); border-color: #4f7be5; position: relative; }}
.checked-box::after {{ content: "✓"; color: white; position: absolute; inset: 0; display: grid; place-items: center; font-size: 16px; font-weight: 700; }}
.task-text {{ font-size: 20px; color: #202938; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 8px; }}
.task-notes {{ color: #64748b; font-size: 14px; margin-bottom: 10px; max-width: 800px; }}
.completed {{ text-decoration: line-through; color: #93a0af; }}
.task-meta {{ display: flex; gap: 8px; flex-wrap: wrap; }}
.meta-chip, .task-tag, .priority-badge {{ display: inline-block; padding: 7px 12px; border-radius: 999px; font-size: 13px; }}
.meta-chip {{ background: #eff3f8; color: #4b5563; }}
.priority-badge.high {{ background: #fee2e2; color: #991b1b; }}
.priority-badge.medium {{ background: #fef3c7; color: #92400e; }}
.priority-badge.low {{ background: #e0f2fe; color: #075985; }}
.task-tag.today {{ background: #dfeee9; color: #42675d; }}
.task-tag.next-week {{ background: #dfe7fb; color: #44578f; }}
.task-tag.due {{ background: #ede9fe; color: #5b21b6; }}
.task-actions {{ display: flex; align-items: center; gap: 10px; margin-left: 18px; flex-shrink: 0; }}
.icon-btn {{ color: #5c6470; text-decoration: none; font-size: 20px; width: 30px; height: 30px; display: inline-grid; place-items: center; border-radius: 8px; }}
.icon-btn:hover {{ background: #f2f5f9; }}
.empty-state {{ background: white; border: 1px dashed #cfd8e3; border-radius: 16px; padding: 24px; color: #64748b; text-align: center; font-size: 17px; }}
.muted {{ margin-top: 22px; color: #8491a3; font-size: 14px; }}
.edit-form {{ display: grid; grid-template-columns: 1.4fr 1.2fr 150px 140px 140px 150px auto; gap: 12px; width: 100%; }}
.edit-task-input {{ min-width: 0; }}
.edit-actions {{ display: flex; gap: 8px; align-items: center; }}
.mini-btn {{ padding: 12px 14px; border-radius: 12px; font-size: 14px; border: none; }}
.mini-btn.primary {{ background: #122a4d; color: white; }}
.mini-btn.ghost {{ background: #eef2f7; color: #334155; display: inline-flex; align-items: center; }}
@media (max-width: 1240px) {{
  .sidebar {{ display: none; }}
  .content {{ padding: 28px; }}
  .add-form {{ min-width: 0; grid-template-columns: 1fr; }}
  .edit-form {{ grid-template-columns: 1fr; }}
  .task-card {{ align-items: flex-start; gap: 12px; }}
}}
</style>
</head>
<body>
<div class="window">
<div class="browser-bar"><div class="dots"><div class="dot red"></div><div class="dot yellow"></div><div class="dot green"></div></div><div class="tab">TaskFlow</div></div>
<div class="app">
<aside class="sidebar">
<div class="brand"><div class="brand-icon">✓</div><div>TaskFlow</div></div>
<a class="nav-item {'active' if project_filter == 'Inbox' else ''}" href="/{build_query('Inbox', sort_by, None, search_term, show_filter)}"><span class="nav-label">{icon_svg('inbox')}<span>Inbox</span></span><span>{stats['open']}</span></a>
<a class="nav-item {'active' if show_filter == 'active' else ''}" href="/{build_query(project_filter, sort_by, None, search_term, 'active')}"><span class="nav-label"><span>🗓</span><span>Active</span></span><span>{stats['open']}</span></a>
<a class="nav-item {'active' if show_filter == 'completed' else ''}" href="/{build_query(project_filter, sort_by, None, search_term, 'completed')}"><span class="nav-label">{icon_svg('completed')}<span>Completed</span></span><span>{stats['completed']}</span></a>
<div class="section-title"><span>▦ Projects</span><span>⌃</span></div>
{''.join(project_links)}
<form class="project-add-form" method="POST" action="/add_project{build_query(project_filter, sort_by, None, search_term, show_filter)}">
<input name="project_name" placeholder="New project name" required>
<button type="submit">＋ Create New Project</button>
</form>
<div class="section-title"><span>📊 Overview</span><span>⌄</span></div>
<div class="stats-grid">
<div class="stat-card"><div class="stat-label">Open</div><div class="stat-value">{stats['open']}</div></div>
<div class="stat-card"><div class="stat-label">Total</div><div class="stat-value">{stats['total']}</div></div>
<div class="stat-card"><div class="stat-label">Done</div><div class="stat-value">{stats['completed']}</div></div>
<div class="stat-card"><div class="stat-label">Due today</div><div class="stat-value">{stats['due_today']}</div></div>
</div>
</aside>
<main class="main">
<div class="topbar">
<form class="search-form" method="GET" action="/">
<input type="hidden" name="project" value="{html.escape(project_filter if project_filter != 'Inbox' else '')}">
<input type="hidden" name="sort" value="{html.escape(sort_by if sort_by != 'manual' else '')}">
<input type="hidden" name="show" value="{html.escape(show_filter if show_filter != 'all' else '')}">
<input class="search" name="q" value="{html.escape(search_term)}" placeholder="Search tasks or notes">
<button class="secondary-btn" type="submit">Search</button>
<a class="clear-link" href="/{build_query(project_filter, sort_by, None, '', show_filter)}">Clear</a>
</form>
</div>
<div class="content">
<div class="header-row">
<h1 class="page-title">{html.escape(project_filter if project_filter != 'Inbox' else 'Inbox')}</h1>
<div class="header-actions">
<a class="secondary-btn" href="/clear_completed{build_query(project_filter, sort_by, None, search_term, show_filter)}">Clear Completed</a>
<button class="add-task-btn" onclick="document.getElementById('task').focus()">＋ Add Task</button>
</div>
</div>
<div class="toolbar">
<form class="add-form" method="POST" action="/add{build_query(project_filter, sort_by, None, search_term, show_filter)}">
<input id="task" name="task" placeholder="Enter a new task..." required>
<select name="project">
{"".join([f"<option value='{html.escape(row['name'])}' {'selected' if row['name'] == (project_filter if project_filter != 'Inbox' else 'Work') else ''}>{html.escape(row['name'])}</option>" for row in projects])}
</select>
<select name="label"><option value="">No Label</option><option value="Today">Today</option><option value="Next Week">Next Week</option></select>
<select name="priority"><option value="Low">Low</option><option value="Medium" selected>Medium</option><option value="High">High</option></select>
<input type="date" name="due_date">
<button class="add-task-btn" type="submit">Add</button>
</form>
</div>
<div class="filter-bar">
<div class="filter-pills">
<a class="pill {'active' if show_filter == 'all' else ''}" href="/{build_query(project_filter, sort_by, None, search_term, 'all')}">All</a>
<a class="pill {'active' if show_filter == 'active' else ''}" href="/{build_query(project_filter, sort_by, None, search_term, 'active')}">Active</a>
<a class="pill {'active' if show_filter == 'completed' else ''}" href="/{build_query(project_filter, sort_by, None, search_term, 'completed')}">Completed</a>
</div>
<div class="sort-label">Search results: <span class="sort-pill">{len(active_tasks)}</span></div>
</div>
<div class="sort-row">
<div class="sort-label">Sort by <span class="sort-pill">{sort_label}</span></div>
<div class="sort-links">
<a class="sort-link {'active' if sort_by == 'manual' else ''}" href="/{build_query(project_filter, 'manual', None, search_term, show_filter)}">Manual</a>
<a class="sort-link {'active' if sort_by == 'date' else ''}" href="/{build_query(project_filter, 'date', None, search_term, show_filter)}">Date</a>
<a class="sort-link {'active' if sort_by == 'priority' else ''}" href="/{build_query(project_filter, 'priority', None, search_term, show_filter)}">Priority</a>
<a class="sort-link {'active' if sort_by == 'label' else ''}" href="/{build_query(project_filter, 'label', None, search_term, show_filter)}">Label</a>
<a class="sort-link {'active' if sort_by == 'due' else ''}" href="/{build_query(project_filter, 'due', None, search_term, show_filter)}">Due Date</a>
</div>
</div>
<div class="task-list">{tasks_html}</div>
<div class="muted">SQLite-backed storage lives in <code>{html.escape(str(DB_FILE.name))}</code>. Your tasks persist across browser closes, app restarts, and server restarts as long as the <code>data/</code> folder remains.</div>
</div>
</main>
</div>
</div>
</body>
</html>'''
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html_page.encode("utf-8"))

    def do_POST(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        project_filter = query.get("project", ["Inbox"])[0]
        sort_by = query.get("sort", ["manual"])[0]
        search_term = query.get("q", [""])[0].strip()
        show_filter = query.get("show", ["all"])[0]

        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8")
        form = parse_qs(post_data)

        with connect_db() as conn:
            if parsed.path == "/add":
                task = form.get("task", [""])[0].strip()
                project = form.get("project", ["Work"])[0].strip()
                label = form.get("label", [""])[0].strip()
                priority = form.get("priority", ["Medium"])[0].strip()
                due_date = parse_due_date(form.get("due_date", [""])[0])
                if task:
                    max_position = conn.execute("SELECT COALESCE(MAX(position), 0) FROM tasks").fetchone()[0]
                    conn.execute(
                        "INSERT INTO tasks (task, notes, project, label, priority, due_date, completed, created_at, position) VALUES (?, '', ?, ?, ?, ?, 0, ?, ?)",
                        (task, project if project else "Work", label if label in LABELS else "", priority if priority in PRIORITIES else "Medium", due_date, now_iso(), max_position + 1),
                    )
                    conn.commit()
                    normalize_positions(conn)
                self.redirect_home(project_filter, sort_by, search_term, show_filter)
                return

            if parsed.path == "/update":
                tid = int(form.get("id", ["0"])[0])
                task = get_task(conn, tid)
                if task:
                    new_text = form.get("task", [task["task"]])[0].strip()
                    new_notes = form.get("notes", [task["notes"]])[0].strip()
                    new_project = form.get("project", [task["project"]])[0].strip()
                    new_label = form.get("label", [task["label"]])[0].strip()
                    new_priority = form.get("priority", [task["priority"]])[0].strip()
                    new_due = parse_due_date(form.get("due_date", [task["due_date"] or ""])[0])
                    if new_text:
                        conn.execute(
                            "UPDATE tasks SET task = ?, notes = ?, project = ?, label = ?, priority = ?, due_date = ? WHERE id = ?",
                            (new_text, new_notes, new_project if new_project else task["project"], new_label if new_label in LABELS else "", new_priority if new_priority in PRIORITIES else task["priority"], new_due, tid),
                        )
                        conn.commit()
                self.redirect_home(project_filter, sort_by, search_term, show_filter)
                return

            if parsed.path == "/add_project":
                project_name = form.get("project_name", [""])[0].strip()
                if project_name:
                    conn.execute("INSERT OR IGNORE INTO projects (name, created_at) VALUES (?, ?)", (project_name, now_iso()))
                    conn.commit()
                self.redirect_home(project_name or project_filter, sort_by, search_term, show_filter)
                return

        self.send_response(404)
        self.end_headers()


if __name__ == "__main__":
    init_db()
    server = HTTPServer(("127.0.0.1", 5000), TodoHandler)
    print("Running on http://127.0.0.1:5000")
    print(f"Using SQLite database at {DB_FILE}")
    server.serve_forever()
