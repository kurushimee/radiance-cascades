# Implementation plans

| Folder | Status |
|---|---|
| `backlog/` | Accepted; work has not started |
| `in_progress/` | Being worked on |
| `finished/` | Done |

## Plan file format

Name: `NNN_<slug>.md`. The three-digit number runs through all folders and is never reused. The file starts with frontmatter:

```markdown
---
id: 001
title: Short title
status: backlog | in_progress | finished
created: YYYY-MM-DD
updated: YYYY-MM-DD
finished: YYYY-MM-DD   (finished plans only)
---
```

Tasks are checkboxes grouped into phases, and each phase states its done criterion. A "Facts / research" section records what was found along the way, so a later session can continue without redoing the research.

## Working rules

1. Before starting new work, check `in_progress/` and `backlog/` for an overlapping plan.
2. When work starts, move the file to `in_progress/` and update `status` and `updated`.
3. While working, tick the checkboxes and update `updated`.
4. When done, move the file to `finished/`, set `finished`, and update `status`.
5. Move lasting knowledge from a finished plan into `docs/`.
