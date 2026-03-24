from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse, urlencode
import html
import datetime

PROJECTS = ["Work", "Personal", "Groceries"]
LABELS = ["Today", "Next Week", "No Label"]
PRIORITIES = ["Low", "Medium", "High"]

todos = [
    {
        "id": 1,
        "task": "Finish project proposal for Client A",
        "project": "Work",
        "label": "",
        "priority": "High",
        "completed": False,
        "created_at": datetime.datetime.now(),
        "position": 1,
    },
    {
        "id": 2,
        "task": "Buy milk and bread",
        "project": "Groceries",
        "label": "Today",
        "priority": "Medium",
        "completed": False,
        "created_at": datetime.datetime.now(),
        "position": 2,
    },
    {
        "id": 3,
        "task": "Schedule dentist appointment",
        "project": "Personal",
        "label": "",
        "priority": "Medium",
        "completed": False,
        "created_at": datetime.datetime.now(),
        "position": 3,
    },
    {
        "id": 4,
        "task": "Review design assets",
        "project": "Work",
        "label": "",
        "priority": "Low",
        "completed": False,
        "created_at": datetime.datetime.now(),
        "position": 4,
    },
    {
        "id": 5,
        "task": "Call Mom",
        "project": "Personal",
        "label": "",
        "priority": "Medium",
        "completed": False,
        "created_at": datetime.datetime.now(),
        "position": 5,
    },
    {
        "id": 6,
        "task": "Update website blog post",
        "project": "Work",
        "label": "Next Week",
        "priority": "Low",
        "completed": False,
        "created_at": datetime.datetime.now(),
        "position": 6,
    },
]

next_id = 7


def priority_rank(value):
    return {"High": 0, "Medium": 1, "Low": 2}.get(value, 3)


def label_rank(value):
    return {"Today": 0, "Next Week": 1, "": 2}.get(value, 3)


def get_task(task_id):
    for t in todos:
        if t["id"] == task_id:
            return t
    return None


def normalize_positions():
    global todos
    todos = sorted(todos, key=lambda x: x["position"])
    for i, task in enumerate(todos, start=1):
        task["position"] = i


def filtered_and_sorted_tasks(project_filter, sort_by):
    items = todos[:]

    if project_filter and project_filter != "Inbox":
        items = [t for t in items if t["project"] == project_filter]

    if sort_by == "date":
        items.sort(key=lambda x: x["created_at"], reverse=True)
    elif sort_by == "priority":
        items.sort(key=lambda x: (priority_rank(x["priority"]), x["position"]))
    elif sort_by == "label":
        items.sort(key=lambda x: (label_rank(x["label"]), x["position"]))
    else:
        items.sort(key=lambda x: x["position"])

    incomplete = [t for t in items if not t["completed"]]
    complete = [t for t in items if t["completed"]]
    return incomplete + complete


def build_query(project_filter, sort_by, editing_id=None):
    params = {}
    if project_filter and project_filter != "Inbox":
        params["project"] = project_filter
    if sort_by and sort_by != "manual":
        params["sort"] = sort_by
    if editing_id is not None:
        params["edit"] = str(editing_id)
    q = urlencode(params)
    return f"?{q}" if q else ""


class TodoHandler(BaseHTTPRequestHandler):
    def redirect_home(self, project_filter="Inbox", sort_by="manual"):
        self.send_response(303)
        self.send_header("Location", "/" + build_query(project_filter, sort_by))
        self.end_headers()

    def do_GET(self):
        global todos
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        project_filter = query.get("project", ["Inbox"])[0]
        sort_by = query.get("sort", ["manual"])[0]
        editing_id = int(query.get("edit", ["0"])[0]) if query.get("edit") else None

        if parsed.path == "/delete":
            tid = int(query.get("id", [0])[0])
            todos = [t for t in todos if t["id"] != tid]
            normalize_positions()
            self.redirect_home(project_filter, sort_by)
            return

        if parsed.path == "/toggle":
            tid = int(query.get("id", [0])[0])
            task = get_task(tid)
            if task:
                task["completed"] = not task["completed"]
            self.redirect_home(project_filter, sort_by)
            return

        if parsed.path == "/move":
            tid = int(query.get("id", [0])[0])
            direction = query.get("dir", [""])[0]
            normalize_positions()
            ordered = sorted(todos, key=lambda x: x["position"])
            idx = next((i for i, t in enumerate(ordered) if t["id"] == tid), None)

            if idx is not None:
                if direction == "up" and idx > 0:
                    ordered[idx]["position"], ordered[idx - 1]["position"] = ordered[idx - 1]["position"], ordered[idx]["position"]
                elif direction == "down" and idx < len(ordered) - 1:
                    ordered[idx]["position"], ordered[idx + 1]["position"] = ordered[idx + 1]["position"], ordered[idx]["position"]

            normalize_positions()
            self.redirect_home(project_filter, sort_by)
            return

        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()

        active_tasks = filtered_and_sorted_tasks(project_filter, sort_by)
        editing_task = get_task(editing_id) if editing_id else None

        task_cards = []
        for t in active_tasks:
            is_editing = editing_task and editing_task["id"] == t["id"]

            if is_editing:
                task_cards.append(f"""
                <div class="task-card editing">
                    <form method="POST" action="/update{build_query(project_filter, sort_by)}" class="edit-form">
                        <input type="hidden" name="id" value="{t['id']}">
                        <input class="edit-task-input" name="task" value="{html.escape(t['task'])}" required>
                        <select name="project">
                            {''.join([f"<option value='{p}' {'selected' if p == t['project'] else ''}>{p}</option>" for p in PROJECTS])}
                        </select>
                        <select name="label">
                            <option value="" {'selected' if t['label'] == '' else ''}>No Label</option>
                            <option value="Today" {'selected' if t['label'] == 'Today' else ''}>Today</option>
                            <option value="Next Week" {'selected' if t['label'] == 'Next Week' else ''}>Next Week</option>
                        </select>
                        <select name="priority">
                            {''.join([f"<option value='{p}' {'selected' if p == t['priority'] else ''}>{p}</option>" for p in PRIORITIES])}
                        </select>
                        <div class="edit-actions">
                            <button class="mini-btn primary" type="submit">Save</button>
                            <a class="mini-btn ghost" href="/{build_query(project_filter, sort_by)}">Cancel</a>
                        </div>
                    </form>
                </div>
                """)
                continue

            label_html = f"<span class='task-tag {t['label'].lower().replace(' ', '-')}'>{html.escape(t['label'])}</span>" if t["label"] else ""
            priority_html = f"<span class='priority-badge {t['priority'].lower()}'>{html.escape(t['priority'])}</span>"
            checked = "checked-box" if t["completed"] else ""
            completed_class = "completed" if t["completed"] else ""

            task_cards.append(f"""
            <div class="task-card">
                <div class="task-left">
                    <a class="checkbox {checked}" href="/toggle?id={t['id']}&project={project_filter}&sort={sort_by}" title="Toggle complete"></a>
                    <div class="task-main">
                        <div class="task-text {completed_class}">{html.escape(t['task'])}</div>
                        <div class="task-meta">
                            <span class="meta-chip">{html.escape(t['project'])}</span>
                            {priority_html}
                            {label_html}
                        </div>
                    </div>
                </div>

                <div class="task-actions">
                    <a class="icon-btn" href="/{build_query(project_filter, sort_by, t['id'])}" title="Edit">✎</a>
                    <a class="icon-btn" href="/delete?id={t['id']}&project={project_filter}&sort={sort_by}" title="Delete">🗑</a>
                    <a class="icon-btn" href="/move?id={t['id']}&dir=up&project={project_filter}&sort={sort_by}" title="Move up">⌃</a>
                    <a class="icon-btn" href="/move?id={t['id']}&dir=down&project={project_filter}&sort={sort_by}" title="Move down">⌄</a>
                </div>
            </div>
            """)

        tasks_html = "\n".join(task_cards) if task_cards else """
        <div class="empty-state">No tasks in this view.</div>
        """

        project_links = []
        for p in PROJECTS:
            active = "sub-item active-sub" if p == project_filter else "sub-item"
            project_links.append(
                f"<a class='{active}' href='/{build_query(p, sort_by)}'><span>📁 {p}</span><span>›</span></a>"
            )

        sort_label = {
            "manual": "Manual",
            "date": "Date",
            "priority": "Priority",
            "label": "Label",
        }.get(sort_by, "Manual")

        html_page = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>TaskFlow</title>
            <style>
                * {{
                    box-sizing: border-box;
                }}

                body {{
                    margin: 0;
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
                    background: #edf1f6;
                    color: #1d2433;
                }}

                a {{
                    text-decoration: none;
                }}

                .window {{
                    max-width: 1240px;
                    margin: 34px auto;
                    background: #f8fafc;
                    border-radius: 18px;
                    overflow: hidden;
                    box-shadow: 0 22px 55px rgba(0, 0, 0, 0.18);
                    border: 1px solid rgba(255,255,255,0.6);
                }}

                .browser-bar {{
                    height: 44px;
                    background: linear-gradient(to bottom, #f7f8fb, #eceff3);
                    display: flex;
                    align-items: center;
                    gap: 14px;
                    padding: 0 14px;
                    border-bottom: 1px solid #dfe5ec;
                }}

                .dots {{
                    display: flex;
                    gap: 8px;
                }}

                .dot {{
                    width: 12px;
                    height: 12px;
                    border-radius: 50%;
                }}

                .red {{ background: #ff5f57; }}
                .yellow {{ background: #febc2e; }}
                .green {{ background: #28c840; }}

                .tab {{
                    background: white;
                    border-radius: 10px 10px 0 0;
                    padding: 9px 16px;
                    font-size: 15px;
                    color: #404856;
                }}

                .app {{
                    display: flex;
                    min-height: 760px;
                }}

                .sidebar {{
                    width: 335px;
                    background:
                        radial-gradient(circle at 20% 10%, rgba(75, 140, 255, 0.22), transparent 24%),
                        linear-gradient(180deg, #122844 0%, #132842 44%, #102238 100%);
                    color: white;
                    padding: 24px 22px 28px;
                }}

                .brand {{
                    display: flex;
                    align-items: center;
                    gap: 14px;
                    font-size: 24px;
                    font-weight: 700;
                    margin-bottom: 34px;
                }}

                .brand-icon {{
                    width: 38px;
                    height: 38px;
                    border-radius: 10px;
                    background: linear-gradient(135deg, #4f89ff, #6aa1ff);
                    display: grid;
                    place-items: center;
                    box-shadow: 0 10px 20px rgba(0,0,0,0.2);
                }}

                .nav-item, .sub-item {{
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    color: rgba(255,255,255,0.9);
                    padding: 14px 16px;
                    border-radius: 14px;
                    margin-bottom: 8px;
                    font-size: 18px;
                }}

                .nav-item:hover, .sub-item:hover {{
                    background: rgba(255,255,255,0.08);
                }}

                .nav-item.active {{
                    background: rgba(255,255,255,0.14);
                }}

                .section-title {{
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 12px 14px;
                    margin-top: 16px;
                    margin-bottom: 8px;
                    font-size: 17px;
                    color: rgba(255,255,255,0.88);
                }}

                .sub-item {{
                    margin-bottom: 4px;
                    padding-left: 24px;
                    font-size: 17px;
                }}

                .active-sub {{
                    background: rgba(255,255,255,0.10);
                }}

                .outline-btn {{
                    display: block;
                    width: 100%;
                    margin-top: 16px;
                    padding: 14px 18px;
                    border: 1px solid rgba(255,255,255,0.28);
                    border-radius: 14px;
                    color: white;
                    background: transparent;
                    font-size: 17px;
                    text-align: left;
                }}

                .main {{
                    flex: 1;
                    background: linear-gradient(180deg, #f8fafc 0%, #eef2f7 100%);
                }}

                .topbar {{
                    height: 74px;
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    padding: 0 34px 0 48px;
                    background: rgba(255,255,255,0.92);
                    border-bottom: 1px solid #e4e9ef;
                    box-shadow: 0 6px 18px rgba(18,34,56,0.05);
                }}

                .search {{
                    width: 430px;
                    background: #eef2f6;
                    border-radius: 999px;
                    padding: 14px 20px;
                    color: #7a8494;
                    font-size: 17px;
                }}

                .avatar {{
                    width: 42px;
                    height: 42px;
                    border-radius: 50%;
                    background: linear-gradient(180deg, #d8dde6, #bcc5d0);
                }}

                .content {{
                    padding: 36px 48px 48px;
                }}

                .header-row {{
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    margin-bottom: 24px;
                }}

                .page-title {{
                    margin: 0;
                    font-size: 54px;
                    font-weight: 700;
                    letter-spacing: -1px;
                    color: #1c2636;
                }}

                .add-task-btn {{
                    background: linear-gradient(180deg, #122a4d, #0e2340);
                    color: white;
                    border: none;
                    border-radius: 14px;
                    padding: 15px 22px;
                    font-size: 18px;
                    box-shadow: 0 10px 20px rgba(14,35,64,0.18);
                    cursor: pointer;
                }}

                .toolbar {{
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    gap: 14px;
                    margin-bottom: 18px;
                    flex-wrap: wrap;
                }}

                .add-form {{
                    display: grid;
                    grid-template-columns: 1.4fr 170px 150px 140px 120px;
                    gap: 12px;
                    flex: 1;
                    min-width: 650px;
                }}

                .add-form input,
                .add-form select,
                .edit-form input,
                .edit-form select {{
                    border: 1px solid #dbe2ea;
                    background: white;
                    border-radius: 14px;
                    padding: 14px 16px;
                    font-size: 15px;
                    outline: none;
                    box-shadow: 0 4px 10px rgba(15, 23, 42, 0.04);
                }}

                .sort-row {{
                    display: flex;
                    justify-content: flex-end;
                    gap: 12px;
                    margin-bottom: 16px;
                    align-items: center;
                }}

                .sort-label {{
                    color: #525c6b;
                    font-size: 16px;
                }}

                .sort-pill {{
                    background: #e9edf3;
                    color: #344054;
                    padding: 8px 12px;
                    border-radius: 10px;
                    font-weight: 600;
                }}

                .sort-links {{
                    display: flex;
                    gap: 10px;
                    flex-wrap: wrap;
                }}

                .sort-link {{
                    color: #5b6574;
                    padding: 8px 10px;
                    border-radius: 10px;
                }}

                .sort-link.active {{
                    background: #e7ecf2;
                    color: #1f2937;
                    font-weight: 600;
                }}

                .task-list {{
                    display: flex;
                    flex-direction: column;
                    gap: 14px;
                }}

                .task-card {{
                    background: white;
                    border-radius: 16px;
                    min-height: 78px;
                    padding: 18px 22px;
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    box-shadow: 0 4px 12px rgba(15, 23, 42, 0.06);
                    border: 1px solid #e8edf4;
                }}

                .task-card.editing {{
                    padding: 16px;
                }}

                .task-left {{
                    display: flex;
                    align-items: center;
                    gap: 16px;
                    min-width: 0;
                    flex: 1;
                }}

                .task-main {{
                    min-width: 0;
                }}

                .checkbox {{
                    width: 28px;
                    height: 28px;
                    border-radius: 8px;
                    border: 2px solid #c9d2dc;
                    background: #fff;
                    display: inline-block;
                    flex-shrink: 0;
                }}

                .checked-box {{
                    background: linear-gradient(180deg, #5f8df9, #4f7be5);
                    border-color: #4f7be5;
                    position: relative;
                }}

                .checked-box::after {{
                    content: "✓";
                    color: white;
                    position: absolute;
                    inset: 0;
                    display: grid;
                    place-items: center;
                    font-size: 16px;
                    font-weight: 700;
                }}

                .task-text {{
                    font-size: 20px;
                    color: #202938;
                    white-space: nowrap;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    margin-bottom: 8px;
                }}

                .completed {{
                    text-decoration: line-through;
                    color: #93a0af;
                }}

                .task-meta {{
                    display: flex;
                    gap: 8px;
                    flex-wrap: wrap;
                }}

                .meta-chip, .task-tag, .priority-badge {{
                    display: inline-block;
                    padding: 7px 12px;
                    border-radius: 999px;
                    font-size: 13px;
                }}

                .meta-chip {{
                    background: #eff3f8;
                    color: #4b5563;
                }}

                .priority-badge.high {{
                    background: #fee2e2;
                    color: #991b1b;
                }}

                .priority-badge.medium {{
                    background: #fef3c7;
                    color: #92400e;
                }}

                .priority-badge.low {{
                    background: #e0f2fe;
                    color: #075985;
                }}

                .task-tag.today {{
                    background: #dfeee9;
                    color: #42675d;
                }}

                .task-tag.next-week {{
                    background: #dfe7fb;
                    color: #44578f;
                }}

                .task-actions {{
                    display: flex;
                    align-items: center;
                    gap: 10px;
                    margin-left: 18px;
                    flex-shrink: 0;
                }}

                .icon-btn {{
                    color: #5c6470;
                    text-decoration: none;
                    font-size: 20px;
                    width: 30px;
                    height: 30px;
                    display: inline-grid;
                    place-items: center;
                    border-radius: 8px;
                }}

                .icon-btn:hover {{
                    background: #f2f5f9;
                }}

                .empty-state {{
                    background: white;
                    border: 1px dashed #cfd8e3;
                    border-radius: 16px;
                    padding: 24px;
                    color: #64748b;
                    text-align: center;
                    font-size: 17px;
                }}

                .muted {{
                    margin-top: 22px;
                    color: #8491a3;
                    font-size: 14px;
                }}

                .edit-form {{
                    display: grid;
                    grid-template-columns: 1.5fr 150px 150px 150px auto;
                    gap: 12px;
                    width: 100%;
                }}

                .edit-task-input {{
                    min-width: 0;
                }}

                .edit-actions {{
                    display: flex;
                    gap: 8px;
                    align-items: center;
                }}

                .mini-btn {{
                    padding: 12px 14px;
                    border-radius: 12px;
                    font-size: 14px;
                    border: none;
                }}

                .mini-btn.primary {{
                    background: #122a4d;
                    color: white;
                }}

                .mini-btn.ghost {{
                    background: #eef2f7;
                    color: #334155;
                    display: inline-flex;
                    align-items: center;
                }}

                @media (max-width: 1180px) {{
                    .sidebar {{
                        display: none;
                    }}

                    .content {{
                        padding: 28px;
                    }}

                    .add-form {{
                        min-width: 0;
                        grid-template-columns: 1fr;
                    }}

                    .edit-form {{
                        grid-template-columns: 1fr;
                    }}

                    .task-card {{
                        align-items: flex-start;
                        gap: 12px;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="window">
                <div class="browser-bar">
                    <div class="dots">
                        <div class="dot red"></div>
                        <div class="dot yellow"></div>
                        <div class="dot green"></div>
                    </div>
                    <div class="tab">TaskFlow</div>
                </div>

                <div class="app">
                    <aside class="sidebar">
                        <div class="brand">
                            <div class="brand-icon">✓</div>
                            <div>TaskFlow</div>
                        </div>

                        <a class="nav-item {'active' if project_filter == 'Inbox' else ''}" href="/{build_query('Inbox', sort_by)}"><span>▢ Inbox</span></a>
                        <a class="nav-item" href="/{build_query('Inbox', 'date')}"><span>🗓 Today</span></a>
                        <a class="nav-item" href="/{build_query('Inbox', 'label')}"><span>🗓 Upcoming</span></a>

                        <div class="section-title">
                            <span>▦ Projects</span>
                            <span>⌃</span>
                        </div>

                        {''.join(project_links)}

                        <button class="outline-btn" type="button">＋ Create New Project</button>

                        <div class="section-title">
                            <span>🏷 Labels</span>
                            <span>⌄</span>
                        </div>

                        <div class="nav-item"><span>⚙ Settings</span></div>
                    </aside>

                    <main class="main">
                        <div class="topbar">
                            <div class="search">🔎 Search</div>
                            <div class="avatar"></div>
                        </div>

                        <div class="content">
                            <div class="header-row">
                                <h1 class="page-title">{html.escape(project_filter if project_filter != 'Inbox' else 'Inbox')}</h1>
                                <button class="add-task-btn" onclick="document.getElementById('task').focus()">＋ Add Task</button>
                            </div>

                            <div class="toolbar">
                                <form class="add-form" method="POST" action="/add{build_query(project_filter, sort_by)}">
                                    <input id="task" name="task" placeholder="Enter a new task..." required>
                                    <select name="project">
                                        {''.join([f"<option value='{p}' {'selected' if p == (project_filter if project_filter != 'Inbox' else 'Work') else ''}>{p}</option>" for p in PROJECTS])}
                                    </select>
                                    <select name="label">
                                        <option value="">No Label</option>
                                        <option value="Today">Today</option>
                                        <option value="Next Week">Next Week</option>
                                    </select>
                                    <select name="priority">
                                        <option value="Low">Low</option>
                                        <option value="Medium" selected>Medium</option>
                                        <option value="High">High</option>
                                    </select>
                                    <button class="add-task-btn" type="submit">Add</button>
                                </form>
                            </div>

                            <div class="sort-row">
                                <div class="sort-label">Sort by <span class="sort-pill">{sort_label}</span></div>
                                <div class="sort-links">
                                    <a class="sort-link {'active' if sort_by == 'manual' else ''}" href="/{build_query(project_filter, 'manual')}">Manual</a>
                                    <a class="sort-link {'active' if sort_by == 'date' else ''}" href="/{build_query(project_filter, 'date')}">Date</a>
                                    <a class="sort-link {'active' if sort_by == 'priority' else ''}" href="/{build_query(project_filter, 'priority')}">Priority</a>
                                    <a class="sort-link {'active' if sort_by == 'label' else ''}" href="/{build_query(project_filter, 'label')}">Label</a>
                                </div>
                            </div>

                            <div class="task-list">
                                {tasks_html}
                            </div>

                            <div class="muted">(Data resets when server restarts)</div>
                        </div>
                    </main>
                </div>
            </div>
        </body>
        </html>
        """

        self.wfile.write(html_page.encode("utf-8"))

    def do_POST(self):
        global todos, next_id
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        project_filter = query.get("project", ["Inbox"])[0]
        sort_by = query.get("sort", ["manual"])[0]

        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8")
        form = parse_qs(post_data)

        if parsed.path == "/add":
            task = form.get("task", [""])[0].strip()
            project = form.get("project", ["Work"])[0].strip()
            label = form.get("label", [""])[0].strip()
            priority = form.get("priority", ["Medium"])[0].strip()

            if task:
                todos.append({
                    "id": next_id,
                    "task": task,
                    "project": project if project in PROJECTS else "Work",
                    "label": label if label in ["Today", "Next Week", ""] else "",
                    "priority": priority if priority in PRIORITIES else "Medium",
                    "completed": False,
                    "created_at": datetime.datetime.now(),
                    "position": len(todos) + 1,
                })
                next_id += 1

            self.redirect_home(project_filter, sort_by)
            return

        if parsed.path == "/update":
            tid = int(form.get("id", ["0"])[0])
            task = get_task(tid)
            if task:
                new_text = form.get("task", [task["task"]])[0].strip()
                new_project = form.get("project", [task["project"]])[0].strip()
                new_label = form.get("label", [task["label"]])[0].strip()
                new_priority = form.get("priority", [task["priority"]])[0].strip()

                if new_text:
                    task["task"] = new_text
                task["project"] = new_project if new_project in PROJECTS else task["project"]
                task["label"] = new_label if new_label in ["Today", "Next Week", ""] else ""
                task["priority"] = new_priority if new_priority in PRIORITIES else task["priority"]

            self.redirect_home(project_filter, sort_by)
            return

        self.send_response(404)
        self.end_headers()


if __name__ == "__main__":
    normalize_positions()
    server = HTTPServer(("127.0.0.1", 5000), TodoHandler)
    print("Running on http://127.0.0.1:5000")
    server.serve_forever()