# Canvas → Obsidian assignment sync

Pulls your upcoming Canvas assignments into your Obsidian vault as markdown
notes, linked to one note per course. Runs on a schedule via GitHub Actions —
no server, no Notion, no Railway.

## How it's organized

```
vault/
  Dashboard.md          <- your home base, with Dataview queries
  Courses/
    Organic Chemistry.md   <- created once, never overwritten — add notes freely
    Intro to Calculus.md
  Assignments/
    Lab Report 3.md      <- fully managed by the script, safe to let it rewrite
    Quiz 4.md
```

Each assignment note links to its course with a real `[[wikilink]]`, and each
course note has a **Dataview** query that automatically lists just its own
assignments. Nothing to drag, nothing to relate manually.

## 1. Install the Dataview plugin (for the auto-lists to work)

In Obsidian: **Settings → Community plugins → Browse** → search **Dataview**
→ Install → Enable. This is what powers the assignment tables on your
Dashboard and course notes.

## 2. Get a Canvas API token

Canvas → **Account → Settings → Approved Integrations → + New Access Token**.
Copy it. Your `CANVAS_BASE_URL` is your school's Canvas domain, e.g.
`https://canvas.yourschool.edu` (no trailing slash).

## 3. Test it locally (optional but smart)

```bash
pip install -r requirements.txt
export CANVAS_BASE_URL="https://canvas.yourschool.edu"
export CANVAS_TOKEN="..."
export VAULT_DIR="vault"
python canvas_to_obsidian.py
```

Check the `vault/Courses` and `vault/Assignments` folders — you should see
new `.md` files appear.

## 4. Put it on autopilot

**A. Push this whole folder to a GitHub repo.** Public is fine and free —
nothing secret lives in the code (your Canvas token stays in encrypted
Secrets). If you'd rather keep it private, GitHub gives 2,000 free
Action-minutes/month, which comfortably covers a 15-minute schedule.

**B. Add your secret:** repo → **Settings → Secrets and variables → Actions
→ New repository secret** → `CANVAS_TOKEN` and `CANVAS_BASE_URL`.

**C. Give the workflow permission to push commits:** repo → **Settings →
Actions → General → Workflow permissions** → select **"Read and write
permissions"** → Save. (Without this, the sync can create files but can't
commit them back — you'd see a "permission denied" error on push.)

**D. Test it:** **Actions** tab → **Sync Canvas to Obsidian vault** → **Run
workflow**. It should turn green and you'll see a new commit in the repo
history with your assignment notes.

## 5. Connect it to your actual vault: Obsidian Git

Right now the synced notes live in the GitHub repo, not automatically inside
your Obsidian app. To close that gap, install the free **Obsidian Git**
community plugin and point your vault at this same repo — then Obsidian Git
can auto-pull the bot's commits on a timer (its own settings has an "auto
pull interval"), and your vault updates itself, same as before.

If you'd rather not set that up yet, you can always just download the
`vault/` folder contents from GitHub and drop them into your vault by hand
whenever you want fresh assignments.

## Notes

- Matching is done by a hidden `canvas_id` in each note's frontmatter, not
  by filename — so you can rename any note in Obsidian and the sync will
  still find it correctly next time.
- Course notes are created once and never touched again, so any notes,
  subpages, or content you add inside them is always safe.
- Assignment notes ARE fully rewritten each run (to keep due dates/done
  status current) — don't put your own notes inside an assignment note;
  put them in the course note instead, or link out to a separate note.
