#!/usr/bin/env python3
"""Build the full-details markdown and the Evaluation Notes section from dogs_data.json."""
import json, datetime

dogs = json.load(open("dogs_data.json"))
GEN_DATE = "2026-08-31"
BIO_ORDER = ["Animal ID", "Breed", "Age", "Sex", "Weight", "Adoption fee",
             "Arrived", "Location", "Level"]

def dog_header(d):
    return f"{d['name']}  ({d['animal_id']})"

# ---------- 1. Full details markdown ----------
lines = []
lines.append("# Maricopa County Animal Care & Control — Adoptable Dogs (Full Details)")
lines.append("")
lines.append(f"Source: https://apps.pets.maricopa.gov/adoptPets/  |  Pulled: {GEN_DATE}  |  {len(dogs)} dogs")
lines.append("")
lines.append("---")
lines.append("")
for d in dogs:
    lines.append(f"## {dog_header(d)}")
    lines.append("")
    for k in BIO_ORDER:
        v = d["bio"].get(k)
        if v:
            lines.append(f"- **{k}:** {v}")
    lines.append("")
    if d["about"]:
        lines.append("**About me**")
        lines.append("")
        lines.append(d["about"])
        lines.append("")
    reqs = [r for r in d["requirements"] if r and r.lower() != "no requirements"]
    lines.append(f"**Requirements:** {', '.join(reqs) if reqs else 'None'}")
    recs = [r for r in d["recommendations"] if r]
    lines.append(f"**Recommendations:** {', '.join(recs) if recs else 'None'}")
    lines.append("")
    # Evaluation comments
    lines.append(f"**Evaluation Comments** ({len(d['evaluation_comments'])})")
    lines.append("")
    for e in d["evaluation_comments"]:
        date = e["date"].strip()
        txt = e["text"].replace("\n", " ").strip()
        lines.append(f"- {date}: {txt}" if date else f"- {txt}")
    lines.append("")
    # Intake notes
    intake = [i for i in d["intake_notes"] if i["text"] and "no intake notes" not in i["text"].lower()]
    if intake:
        lines.append("**Intake Notes**")
        lines.append("")
        for i in intake:
            date = i["date"].strip()
            txt = i["text"].replace("\n", " ").strip()
            lines.append(f"- {date}: {txt}" if date else f"- {txt}")
        lines.append("")
    # Medical
    if d["medical_treatments"]:
        lines.append(f"**Medical Treatments** ({len(d['medical_treatments'])})")
        lines.append("")
        for m in d["medical_treatments"]:
            date = m["date"].strip()
            txt = m["text"].replace("\n", " ").strip()
            lines.append(f"- {date}: {txt}" if date else f"- {txt}")
        lines.append("")
    lines.append("---")
    lines.append("")

open("dogs_full_details.md", "w").write("\n".join(lines))
print("Wrote dogs_full_details.md")

# ---------- 2. Evaluation Notes section (appended to notes.txt) ----------
ev_lines = []
ev_lines.append("")
ev_lines.append("=" * 70)
ev_lines.append("## Evaluation Notes")
ev_lines.append(f"(Auto-collected {GEN_DATE} from apps.pets.maricopa.gov — "
                f"{len(dogs)} dogs, "
                f"{sum(len(d['evaluation_comments']) for d in dogs)} evaluation comments)")
ev_lines.append("=" * 70)
ev_lines.append("")
for d in dogs:
    ev_lines.append(f"### {dog_header(d)}")
    breed = d["bio"].get("Breed", "")
    age = d["bio"].get("Age", "")
    sex = d["bio"].get("Sex", "")
    level = d["bio"].get("Level", "")
    meta = " | ".join(x for x in [breed, age, sex, f"Level {level}" if level else ""] if x)
    if meta:
        ev_lines.append(meta)
    if not d["evaluation_comments"]:
        ev_lines.append("  (no evaluation comments)")
    for e in d["evaluation_comments"]:
        date = e["date"].strip()
        txt = e["text"].replace("\n", " ").strip()
        ev_lines.append(f"  - {date}: {txt}" if date else f"  - {txt}")
    ev_lines.append("")

open("evaluation_notes.txt", "w").write("\n".join(ev_lines))
print("Wrote evaluation_notes.txt")

# Append to notes.txt (preserve existing content)
existing = open("notes.txt", encoding="utf-8").read()
if "## Evaluation Notes" in existing:
    # replace everything from the marker onward
    existing = existing.split("\n" + "=" * 70 + "\n## Evaluation Notes")[0].rstrip() + "\n"
    # fallback simple split
    idx = existing.find("## Evaluation Notes")
    if idx != -1:
        existing = existing[:idx].rstrip() + "\n"
with open("notes.txt", "w", encoding="utf-8") as f:
    f.write(existing.rstrip() + "\n" + "\n".join(ev_lines))
print("Appended Evaluation Notes section to notes.txt")
