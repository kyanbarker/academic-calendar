"""List each VEVENT in cal.ics: title, datetime, description, location, repeat.

Usage: python list_events.py [cal.ics]
Writes events.csv and events.md next to this script.
"""
import csv
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).parent


def unfold(text):
    # RFC 5545: a line starting with space/tab continues the previous line
    return re.sub(r"\r?\n[ \t]", "", text).splitlines()


def unescape(v):
    return (v.replace("\\n", "\n").replace("\\N", "\n")
             .replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\"))


def parse_dt(params, value):
    if "VALUE=DATE" in params or len(value) == 8:
        return datetime.strptime(value, "%Y%m%d").date()
    return datetime.strptime(value.rstrip("Z"), "%Y%m%dT%H%M%S")


def parse_events(path):
    events, cur = [], None
    for line in unfold(Path(path).read_text(encoding="utf-8")):
        if line == "BEGIN:VEVENT":
            cur = {}
        elif line == "END:VEVENT":
            events.append(cur)
            cur = None
        elif cur is not None and ":" in line:
            head, value = line.split(":", 1)
            name, *params = head.split(";")
            cur.setdefault(name, []).append((params, value))
    return events


def fmt_when(ev):
    sp, sv = ev["DTSTART"][0]
    start = parse_dt(sp, sv)
    end = parse_dt(*ev["DTEND"][0]) if "DTEND" in ev else None
    if isinstance(start, date) and not isinstance(start, datetime):
        # all-day: DTEND is exclusive
        last = end - timedelta(days=1) if end else start
        return start.isoformat() if last == start else f"{start} to {last}"
    return f"{start:%Y-%m-%d %H:%M}" + (f" to {end:%Y-%m-%d %H:%M}" if end else "")


def get(ev, key):
    return " | ".join(unescape(v) for _, v in ev.get(key, []))


def clean_desc(s):
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return "; ".join(p.strip() for p in s.splitlines() if p.strip())


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else HERE / "cal.ics"
    rows = []
    for ev in parse_events(src):
        repeat = "; ".join(filter(None, [get(ev, "RRULE"), get(ev, "RDATE"),
                                         get(ev, "EXDATE") and "EXDATE " + get(ev, "EXDATE")]))
        rows.append({
            "title": get(ev, "SUMMARY"),
            "datetime": fmt_when(ev),
            "description": clean_desc(get(ev, "DESCRIPTION")),
            "location": get(ev, "LOCATION"),
            "repeat": repeat or "none",
            "categories": get(ev, "CATEGORIES"),
            "uid": get(ev, "UID"),
        })
    rows.sort(key=lambda r: r["datetime"])

    with open(HERE / "events.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)

    cols = ["title", "datetime", "description", "location", "repeat", "categories"]
    esc = lambda s: s.replace("|", "\\|")
    with open(HERE / "events.md", "w", encoding="utf-8") as f:
        f.write(f"# Northeastern Academic Calendar events ({len(rows)})\n\n")
        f.write("| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n")
        for r in rows:
            f.write("| " + " | ".join(esc(r[c]) for c in cols) + " |\n")

    print(f"{len(rows)} events -> events.csv, events.md")


if __name__ == "__main__":
    main()
