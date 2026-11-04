# Prompt

Prompt:

my university has an academic calendar that i subscribe to in google calendar so that the academic calendar in my phone stays up to date when the university adds events to that calendar. however, the academic calendar does not create different ics links for different students. the ics link that the university provides contains calendar events for different types of students (eg grad vs undergrad). i want to be able to have a calendar that is just the academic calendar events relevant to me, an undergrad. we can assume either: 1. events relevant to me can be defined by 1 or more regex; or 2. events not relevant to me can be defined by 1 or more regex. how could i accomplish this. im assuming the ics link that i subscribed to is a url to a server that provides the ics file and thus calendar events. i dont think i can host a server but i could have a script that generates an ics file that is the desired subset of academic events. talk to me about this

---

Response:

Your assumption is right: a subscribed ICS link is just a URL that returns a text file, and Google Calendar re-fetches it periodically. The catch is that Google subscribes to a URL, not a file on your laptop, so the real question is where the filtered file lives and what keeps it fresh. The filtering itself is the easy part.

## The core constraint

Google Calendar can't subscribe to something on your machine, and it can't run your script. So you need:

1. Something that **fetches** the university ICS, **filters** it, and **writes** the result, on a schedule.
2. Somewhere **publicly reachable by URL** to put the output.

You don't need a server for either. Static hosting plus a scheduled job covers it.

## Best option: GitHub Actions + GitHub Pages

This is free, needs no machine of yours to stay on, and is about the most robust setup.

- A repo contains your Python script and a workflow file.
- A scheduled workflow (cron, e.g. every 6 hours) runs the script, which downloads the university ICS, filters it, and writes `undergrad.ics`.
- The workflow commits the output, or deploys it, to GitHub Pages.
- You subscribe in Google Calendar to `https://yourname.github.io/repo/undergrad.ics`.

Alternatives for the "where does it live" part:
- **Cloudflare Workers** (free tier): this *is* a tiny server, but you don't host anything. It fetches and filters on each request, so it's always fresh. Slightly more setup, but the filtering happens live rather than on a cron.
- **Any static host** (Netlify, S3, your university's personal web space) with a cron job elsewhere.
- **A home machine or Raspberry Pi** with cron plus a public path. This works but is more fragile.

One privacy note: the output URL is public (anyone with the link can read it). For a filtered academic calendar that's almost certainly fine, since the source is already public.

## The filtering script

Python with the `icalendar` library is the cleanest route. Roughly:

```python
import re
import requests
from icalendar import Calendar

SOURCE = "https://university.edu/academic-calendar.ics"

# Option 1: keep only events matching these
INCLUDE = [re.compile(p, re.I) for p in [r"undergrad", r"\ball students\b"]]
# Option 2: drop events matching these
EXCLUDE = [re.compile(p, re.I) for p in [r"\bgrad(uate)?\b", r"law school", r"\bPhD\b"]]

def keep(event):
    text = f"{event.get('SUMMARY', '')} {event.get('DESCRIPTION', '')}"
    if any(p.search(text) for p in EXCLUDE):
        return False
    return True   # or: return any(p.search(text) for p in INCLUDE)

cal = Calendar.from_ical(requests.get(SOURCE, timeout=30).content)
out = Calendar()
for k, v in cal.items():          # copy calendar-level props (PRODID, X-WR-CALNAME...)
    out.add(k, v)
for comp in cal.walk():
    if comp.name == "VEVENT":
        if keep(comp):
            out.add_component(comp)
    elif comp.name == "VTIMEZONE":
        out.add_component(comp)

open("undergrad.ics", "wb").write(out.to_ical())
```

## Design decisions worth thinking about

**Include-list vs exclude-list.** This matters more than it seems:
- *Include-list* is safer against noise but can silently drop new events whose titles don't match your patterns (e.g. a generic "Last day to add classes" with no audience label).
- *Exclude-list* never loses a generic event, but a new grad-only event with unexpected wording will leak through.

A combination often works best: exclude things clearly not yours, and treat unlabeled events as relevant. Which failure is worse for you (missing a deadline vs. seeing an extra irrelevant one) should drive the choice. Missing a deadline is usually worse, which favors the exclude-list.

**Match on more than the title.** Check `SUMMARY`, `DESCRIPTION`, `CATEGORIES`, and `LOCATION`. Some university calendars tag audience in `CATEGORIES` or a description prefix like "[Graduate]", which is much more reliable than regexing titles. Download the raw ICS and look at what fields actually distinguish events before writing patterns.

**Preserve UIDs.** Don't rewrite them. Google uses `UID` to track events, so stable UIDs mean edits and cancellations from the university propagate correctly instead of creating duplicates.

**Recurring events.** If the source uses `RRULE`, `EXDATE`, or `RECURRENCE-ID` overrides, keep the master and its overrides together (same UID) or recurrences will break. Filtering by UID rather than per-component is the safe approach: decide per UID, then keep every component with that UID.

**Timezones.** Keep the `VTIMEZONE` blocks, or events with `TZID` references can shift.

**Deleted events.** Since you regenerate the whole file each run, events the university removes disappear from your output too, which is what you want.

**Refresh lag.** Google Calendar polls subscribed ICS feeds on its own schedule, typically every 12 to 24 hours, and you can't force it. So running your cron more often than every few hours buys you little. Once or twice a day is plenty.

**Failure handling.** If the university's server is down or returns garbage, make the script exit with an error rather than writing an empty file, so you don't wipe your calendar. In GitHub Actions a failed run simply leaves the previous good file in place.

## Practical next steps

1. Download the university ICS and inspect it (`grep -E "SUMMARY|CATEGORIES" file.ics | sort | uniq`) to see how audience is signaled.
2. Prototype the regexes locally and diff the output against the original to see what's being dropped.
3. Move it into a GitHub repo with a scheduled workflow and Pages, then swap your phone's subscription from the university link to yours.

If you'd like, I can write the full repo for you: the script, the GitHub Actions workflow, and Pages setup. If you paste a sample of the raw ICS (or just a list of event titles), I can also help draft the regexes.

---
