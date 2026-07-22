#!/usr/bin/env python3
"""
canvas_to_obsidian.py
Sync upcoming Canvas assignments into an Obsidian vault as markdown notes.

Writes two kinds of notes:
  vault/Courses/<Course Name>.md      — one per active course, CREATED ONCE
                                         and never overwritten again, so your
                                         own notes/subpages inside it are safe.
  vault/Assignments/<Title>.md        — one per assignment, fully managed by
                                         this script (safe to let it rewrite).

Matching is done on Canvas IDs stored in each note's frontmatter, so re-runs
update in place rather than creating duplicates, and renaming a course or
assignment note in Obsidian does not break the link.

Required environment variables:
  CANVAS_BASE_URL   e.g. https://canvas.yourschool.edu   (no trailing slash)
  CANVAS_TOKEN      Canvas API access token
  VAULT_DIR         path to the vault checkout, e.g. "vault"

Optional:
  DAYS_AHEAD        how many days of upcoming items to sync (default 60)
"""

import os
import re
import sys
import requests
from datetime import datetime, timezone, timedelta

CANVAS_BASE_URL = os.environ.get("CANVAS_BASE_URL", "").rstrip("/")
CANVAS_TOKEN = os.environ.get("CANVAS_TOKEN", "")
VAULT_DIR = os.environ.get("VAULT_DIR", "vault")
DAYS_AHEAD = int(os.environ.get("DAYS_AHEAD", "60"))

COURSES_DIR = os.path.join(VAULT_DIR, "Courses")
ASSIGNMENTS_DIR = os.path.join(VAULT_DIR, "Assignments")

TYPE_LABELS = {
    "assignment": "Assignment",
    "quiz": "Quiz",
    "discussion_topic": "Discussion",
    "wiki_page": "Page",
    "sub_assignment": "Assignment",
}

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)
ILLEGAL_CHARS = re.compile(r'[\\/:*?"<>|#^\[\]]')


def require_env():
    missing = [k for k, v in {
        "CANVAS_BASE_URL": CANVAS_BASE_URL,
        "CANVAS_TOKEN": CANVAS_TOKEN,
    }.items() if not v]
    if missing:
        sys.exit(f"Missing required env vars: {', '.join(missing)}")


def safe_filename(name, maxlen=120):
    name = ILLEGAL_CHARS.sub("", name).strip()
    return name[:maxlen] if name else "Untitled"


# ---------- Canvas ----------
def canvas_get(path, params=None):
    url = f"{CANVAS_BASE_URL}/api/v1/{path.lstrip('/')}"
    headers = {"Authorization": f"Bearer {CANVAS_TOKEN}"}
    params = dict(params or {})
    params.setdefault("per_page", 100)
    results = []
    while url:
        r = requests.get(url, headers=headers, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        results.extend(data if isinstance(data, list) else [data])
        url, params = None, None
        for part in r.headers.get("Link", "").split(","):
            seg = part.split(";")
            if len(seg) >= 2 and 'rel="next"' in seg[1]:
                url = seg[0].strip().strip("<>")
    return results


def get_course_names():
    courses = canvas_get("courses", {"enrollment_state": "active"})
    return {c["id"]: c.get("name", f"Course {c['id']}") for c in courses if "id" in c}


def get_upcoming_items():
    start = datetime.now(timezone.utc)
    end = start + timedelta(days=DAYS_AHEAD)
    items = canvas_get("planner/items", {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    })
    keep = {"assignment", "quiz", "discussion_topic", "wiki_page", "sub_assignment"}
    out = {}
    for it in items:
        ptype = it.get("plannable_type", "")
        if ptype not in keep:
            continue
        p = it.get("plannable", {}) or {}
        due = p.get("due_at") or p.get("todo_date") or it.get("plannable_date")
        html_url = it.get("html_url", "")
        if html_url.startswith("/"):
            html_url = CANVAS_BASE_URL + html_url
        canvas_id = str(it.get("plannable_id") or p.get("id") or "")
        if not canvas_id:
            continue
        subs = it.get("submissions")
        out[canvas_id] = {
            "canvas_id": canvas_id,
            "title": (p.get("title") or p.get("name") or "(untitled)")[:200],
            "course_id": it.get("course_id"),
            "due": due,
            "type": ptype,
            "url": html_url,
            "done": bool(subs.get("submitted")) if isinstance(subs, dict) else False,
        }
    return list(out.values())


# ---------- vault helpers ----------
def find_note_by_canvas_id(directory, canvas_id):
    """Scan a directory's frontmatter for a matching canvas_id. Returns the
    path if found, else None. Lets you rename notes freely in Obsidian
    without breaking the sync's ability to find them again."""
    if not os.path.isdir(directory):
        return None
    needle = f'canvas_id: "{canvas_id}"'
    for fname in os.listdir(directory):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(directory, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                head = f.read(2000)
        except OSError:
            continue
        if needle in head:
            return fpath
    return None


def upsert_course_note(course_id, name):
    """Create the course note once; never touch it again after that (so the
    student's own content inside it is always safe)."""
    os.makedirs(COURSES_DIR, exist_ok=True)
    existing = find_note_by_canvas_id(COURSES_DIR, course_id)
    if existing:
        return existing

    fname = safe_filename(name) + ".md"
    fpath = os.path.join(COURSES_DIR, fname)
    # Guard against filename collisions with a different course.
    n = 2
    while os.path.exists(fpath):
        fpath = os.path.join(COURSES_DIR, f"{safe_filename(name)} ({n}).md")
        n += 1

    content = f"""---
tags: [course]
canvas_id: "{course_id}"
---

# {name}

*This note was created by the Canvas sync and won't be touched again — add your own lecture notes, syllabus, and subpages below freely.*

## Assignments

```dataview
TABLE due AS "Due", type AS "Type", done AS "Done"
FROM "Assignments"
WHERE course = this.file.link
SORT due ASC
```

## Notes

-
"""
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(content)
    return fpath


def upsert_assignment_note(item, course_note_path):
    """Fully manage this note: overwrite its frontmatter + body every run."""
    os.makedirs(ASSIGNMENTS_DIR, exist_ok=True)
    existing = find_note_by_canvas_id(ASSIGNMENTS_DIR, item["canvas_id"])

    course_name = os.path.splitext(os.path.basename(course_note_path))[0] if course_note_path else ""
    course_link = f"[[{course_name}]]" if course_name else ""
    due_line = f"due: {item['due'][:10]}\n" if item["due"] else ""
    type_label = TYPE_LABELS.get(item["type"], item["type"])

    content = f"""---
tags: [assignment]
canvas_id: "{item['canvas_id']}"
course: "{course_link}"
{due_line}type: {type_label}
done: {str(item['done']).lower()}
url: "{item['url']}"
---

# {item['title']}

Linked to: {course_link}
"""
    if existing:
        fpath = existing
    else:
        fname = safe_filename(item["title"]) + ".md"
        fpath = os.path.join(ASSIGNMENTS_DIR, fname)
        n = 2
        while os.path.exists(fpath) and find_note_by_canvas_id(ASSIGNMENTS_DIR, item["canvas_id"]) != fpath:
            fpath = os.path.join(ASSIGNMENTS_DIR, f"{safe_filename(item['title'])} ({n}).md")
            n += 1

    with open(fpath, "w", encoding="utf-8") as f:
        f.write(content)
    return fpath, existing is not None


def main():
    require_env()

    print("Fetching active Canvas courses...")
    course_names = get_course_names()
    print(f"  {len(course_names)} courses")

    print(f"Fetching Canvas items due in the next {DAYS_AHEAD} days...")
    items = get_upcoming_items()
    print(f"  {len(items)} items")

    print("Syncing course notes...")
    course_note_paths = {}
    for course_id, name in course_names.items():
        course_note_paths[course_id] = upsert_course_note(course_id, name)
    print(f"  {len(course_note_paths)} course notes ready")

    created = updated = 0
    for it in items:
        course_note_path = course_note_paths.get(it["course_id"])
        _, was_existing = upsert_assignment_note(it, course_note_path)
        if was_existing:
            updated += 1
        else:
            created += 1

    print(f"Done. Created {created}, updated {updated}.")


if __name__ == "__main__":
    main()
