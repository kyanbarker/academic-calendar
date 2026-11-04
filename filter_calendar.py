"""Filter the Northeastern academic calendar down to undergrad-relevant events.

Rule (per event SUMMARY, case-insensitive):
    keep if it matches INCLUDE, else drop if it matches EXCLUDE, else keep.
Unlabeled events (breaks, finals, holidays) are kept so no deadline is lost.

Usage:
    python filter_calendar.py                 # fetch live feed -> undergrad.ics
    python filter_calendar.py cal.ics         # use a local file instead
    python filter_calendar.py SRC -o out.ics
Event blocks are copied verbatim, so UIDs and all fields are preserved.
"""
import argparse
import re
import sys
import urllib.request
from pathlib import Path

SOURCE_URL = ("https://25livepub.collegenet.com/calendars/"
              "Northeastern-Academic-Calendar.ics?mixout=418192%2c418415")

INCLUDE = re.compile(r"undergraduate|full-semester", re.I)
# (?<!under)graduate = "graduate" not preceded by "under"
EXCLUDE = re.compile(r"school of law|session|-third|(?<!under)graduate", re.I)


def keep(summary):
    return bool(INCLUDE.search(summary)) or not EXCLUDE.search(summary)


def load(src):
    if re.match(r"(https?|webcal)://", src):
        url = re.sub(r"^webcal://", "https://", src)
        req = urllib.request.Request(url, headers={"User-Agent": "calendar-filter"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read().decode("utf-8")
    return Path(src).read_text(encoding="utf-8")


def summary_of(block):
    unfolded = re.sub(r"\r?\n[ \t]", "", "\n".join(block))
    m = re.search(r"^SUMMARY[^:]*:(.*)$", unfolded, re.M)
    return m.group(1).replace("\\,", ",").replace("\\;", ";") if m else ""


def filter_ics(text):
    out, block, kept, total = [], None, [], 0
    for line in text.splitlines():
        if line == "BEGIN:VEVENT":
            block = [line]
        elif block is not None:
            block.append(line)
            if line == "END:VEVENT":
                total += 1
                s = summary_of(block)
                if keep(s):
                    out.extend(block)
                    kept.append(s)
                block = None
        elif line.startswith("X-WR-CALNAME:"):
            out.append(line + " (Undergrad)")
        else:
            out.append(line)  # calendar header/footer, VTIMEZONE, etc.
    return "\r\n".join(out) + "\r\n", kept, total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", nargs="?", default=SOURCE_URL)
    ap.add_argument("-o", "--out", default="undergrad.ics")
    args = ap.parse_args()

    text = load(args.src)
    if "BEGIN:VCALENDAR" not in text:
        sys.exit("source is not an iCalendar file; not writing output")
    result, kept, total = filter_ics(text)
    if total == 0 or not kept:
        sys.exit(f"no events kept ({total} in source); not writing output")

    Path(args.out).write_bytes(result.encode("utf-8"))
    print(f"kept {len(kept)} of {total} events -> {args.out}")


if __name__ == "__main__":
    main()
