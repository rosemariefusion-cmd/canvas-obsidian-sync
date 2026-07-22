---
tags: [dashboard]
---

# 🎓 Student Dashboard

> ⭐ *Success doesn't come from what you do occasionally — it comes from what you do consistently.*

## ☑️ Reminders
- [ ] Stay hydrated
- [ ] Move your body
- [ ] Charge devices
- [ ] Take a breather

## 📚 Courses

```dataview
TABLE
	length(filter(file.inlinks, (l) => contains(l.file.folder, "Assignments"))) AS "Assignments"
FROM "Courses"
SORT file.name ASC
```

## 📅 Upcoming Assignments

```dataview
TABLE course AS "Course", due AS "Due", type AS "Type", done AS "Done"
FROM "Assignments"
WHERE due
SORT due ASC
```

## ⏰ Overdue

```dataview
TABLE course AS "Course", due AS "Due"
FROM "Assignments"
WHERE due AND due < date(today) AND !done
SORT due ASC
```

## ⚡ Quick Tasks
- [ ] Finalise assignment
- [ ]
