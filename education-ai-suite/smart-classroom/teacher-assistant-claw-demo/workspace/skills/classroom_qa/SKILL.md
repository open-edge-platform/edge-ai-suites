---
name: classroom_qa
description: "Use for Smart Classroom questions: topics covered, class summary, today's class, a specific date, absentee catch-up, transcript details, student engagement, participation, hand raises, or class statistics from $HOME/.openclaw/workspace/smart_classroom_incoming."

---

# Classroom QA


Use this skill for any parent/teacher question about a Smart Classroom session.


Data root:

```text

$HOME/.openclaw/workspace/smart_classroom_incoming
```

## Required Workflow

### 1. Identify the requested date

Interpret the user query.

- "today" means today's date.
- "yesterday" means yesterday's date.
- Specific dates must be normalized to both forms:
  - `YYYY-MM-DD`
  - `YYYYMMDD`
- If no date is mentioned, use the newest session folder.

### 2. List candidate session folders

Always use `bash` before answering.

If a date is requested, run a command like this, replacing the two date variables:

```bash
base=$HOME/.openclaw/workspace/smart_classroom_incoming; d1=YYYY-MM-DD; d2=YYYYMMDD; find "$base" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %f %p\n' 2>/dev/null | awk -v d1="$d1" -v d2="$d2" '$2 ~ "^" d1 || $2 ~ "^" d2' | sort -nr

```

If no date is requested, run:

```bash

find $HOME/.openclaw/workspace/smart_classroom_incoming -mindepth 1 -maxdepth 1 -type d -printf '%T@ %f %p\n' 2>/dev/null | sort -nr
```

Select the newest matching folder. Folder names may have suffixes after the date; do not reject them only because of suffixes.

If no matching folder exists, reply:

```text
No class session has been recorded for that date.
```

If no folders exist at all, reply:

```text
No class session has been recorded yet.

```

### 3. Inspect available files

Use `bash` to list files in the selected folder.

Expected files may include:

```text
summary.md
topics.json
engagement_report.json
```

Read `topics.json` first if present.

### 4. Answer by question type

#### Summary / what happened / today's class summary


Read:


```text
summary.md
```

Use `summary.md` as the main source.

Read `topics.json` only if:

- `summary.md` is missing
- the user also asks for topics
- the user asks for timestamps

Never answer a summary question mainly from `topics.json` when `summary.md` exists.

#### Topics covered / topics discussed

Read:

```text
topics.json
```

Use `topics.json` as the main source. Include timestamps only if present.

Read `summary.md` only if a short overview is needed.

#### Today's class / class on a date

If the user asks for a summary, follow the Summary rule.

If the user asks for topics, follow the Topics rule.

If the user asks generally what happened today, read:

```text
summary.md
```

Then optionally read `topics.json` only for a short topic list.

#### Absentee catch-up

Read:

```text
summary.md
topics.json

```

Use `summary.md` first. Use `topics.json` for the catch-up order.

Give:

- what was taught
- key takeaways
- suggested catch-up order

Do not add outside subject knowledge.

#### Engagement

Read:

```text
engagement_report.json
```

Report only values present, such as talk time, questions, attendance, and hand raises.

#### Participation

Read:

```text
participation_report.json

```

Preserve the order in the file. Do not invent students or counts.

#### Transcript details

Only if the user asks for exact wording, quotes, or detailed discussion:

1. Find transcript file using `ls`.
2. Read targeted parts only.
3. Avoid loading huge transcript content.
4. Use `grep`, `sed`, or short excerpts when possible.
