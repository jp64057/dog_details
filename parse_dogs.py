#!/usr/bin/env python3
"""Parse Maricopa County ACC dog detail pages into structured data + markdown."""
import os, re, json, html, glob
from html.parser import HTMLParser

DETAILS_DIR = "details"

def unescape(s):
    if s is None:
        return ""
    s = html.unescape(s)
    # normalize windows line breaks encoded as literal
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"[ \t]+", " ", s).strip()

class DogParser(HTMLParser):
    """Collect (tag, attrs, text) stream, then post-process."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.events = []  # ('start', tag, attrs) / ('end', tag) / ('data', text)
    def handle_starttag(self, tag, attrs):
        self.events.append(("start", tag, dict(attrs)))
    def handle_endtag(self, tag):
        self.events.append(("end", tag, None))
    def handle_data(self, data):
        if data.strip():
            self.events.append(("data", data, None))

def get_class(attrs):
    return attrs.get("class", "") if attrs else ""

def parse_dog(hcontent):
    p = DogParser()
    p.feed(hcontent)
    ev = p.events

    dog = {}

    # ---- Bio fields: detailInfoBox -> <p> Label <span> Value ----
    # Walk events; when we see a div with class containing detailInfoBox, the next
    # data is the label, and the data inside following span is the value.
    bio = {}
    i = 0
    n = len(ev)
    while i < n:
        kind, a, b = ev[i]
        if kind == "start" and a == "div" and "detailInfoBox" in get_class(b):
            # inside: <p> Label <span> Value </span> </p>. Capture label = first
            # data before the span; value = data inside span; stop at </p>.
            label = None
            value_parts = []
            j = i + 1
            seen_span = False
            while j < n:
                k2, a2, b2 = ev[j]
                if k2 == "end" and a2 == "p":
                    break
                if k2 == "start" and a2 == "div" and "detailInfoBox" in get_class(b2):
                    break
                if k2 == "data":
                    if label is None and not seen_span:
                        label = a2.strip()
                    elif seen_span:
                        value_parts.append(a2.strip())
                if k2 == "start" and a2 == "span":
                    seen_span = True
                j += 1
            if label:
                bio[label] = unescape(" ".join([v for v in value_parts if v]))
        i += 1
    # "About me" is a wide detailInfoBox, not a card — split it out of bio
    about_bio = bio.pop("About me", "")
    dog["bio"] = bio

    # ---- Cards: card-header (title) + following card-body ----
    cards = {}
    i = 0
    while i < n:
        kind, a, b = ev[i]
        if kind == "start" and a == "div" and "card-header" in get_class(b):
            # title = concatenated data until end of this div
            title_parts = []
            j = i + 1
            depth = 1
            while j < n and depth > 0:
                k2, a2, b2 = ev[j]
                if k2 == "start" and a2 == "div":
                    depth += 1
                elif k2 == "end" and a2 == "div":
                    depth -= 1
                elif k2 == "data" and depth >= 1:
                    title_parts.append(a2.strip())
                j += 1
            title = unescape(" ".join(title_parts))
            # find next card-body
            body_start = None
            k = j
            while k < n:
                k2, a2, b2 = ev[k]
                if k2 == "start" and a2 == "div" and "card-body" in get_class(b2):
                    body_start = k
                    break
                # stop if we hit another card-header (empty body)
                if k2 == "start" and a2 == "div" and "card-header" in get_class(b2):
                    break
                k += 1
            body_events = []
            if body_start is not None:
                depth = 1
                k = body_start + 1
                while k < n and depth > 0:
                    k2, a2, b2 = ev[k]
                    if k2 == "start" and a2 == "div":
                        depth += 1
                    elif k2 == "end" and a2 == "div":
                        depth -= 1
                    if depth > 0:
                        body_events.append(ev[k])
                    k += 1
            cards[title] = body_events
        i += 1

    def card_by_prefix(prefix):
        for t, bevs in cards.items():
            if t.lower().startswith(prefix.lower()):
                return t, bevs
        return None, None

    # About me: comes from the wide detailInfoBox captured above
    dog["about"] = about_bio

    # Requirements / Recommendations: list of non-empty data lines
    def list_items(prefix):
        _, bevs = card_by_prefix(prefix)
        if not bevs:
            return []
        items = [unescape(a) for k, a, b in bevs if k == "data" and a.strip()]
        # drop placeholder "No requirements"
        return [x for x in items if x]
    dog["requirements"] = list_items("Requirements")
    dog["recommendations"] = list_items("Recommendations")

    # Dated sections (Evaluation Comments, Medical Treatments): fw-bold date + span text
    def dated_entries(prefix):
        _, bevs = card_by_prefix(prefix)
        if not bevs:
            return []
        entries = []
        m = len(bevs)
        idx = 0
        while idx < m:
            k, a, b = bevs[idx]
            if k == "start" and a == "span" and "fw-bold" in get_class(b):
                # date = next data
                date = ""
                jj = idx + 1
                while jj < m:
                    if bevs[jj][0] == "data":
                        date = unescape(bevs[jj][1])
                        break
                    jj += 1
                # text = data inside following (non fw-bold) span(s) until next fw-bold span
                texts = []
                kk = jj + 1
                while kk < m:
                    k2, a2, b2 = bevs[kk]
                    if k2 == "start" and a2 == "span" and "fw-bold" in get_class(b2):
                        break
                    if k2 == "data":
                        texts.append(unescape(a2))
                    kk += 1
                entries.append({"date": date, "text": " ".join(t for t in texts if t).strip()})
                idx = kk
                continue
            idx += 1
        return entries

    dog["evaluation_comments"] = dated_entries("Evaluation Comments")
    dog["medical_treatments"] = dated_entries("Medical Treatments")

    # Intake Notes: could be dated or plain
    intake = dated_entries("Intake Notes")
    if not intake:
        _, bevs = card_by_prefix("Intake Notes")
        txt = unescape(" ".join(a for k, a, b in (bevs or []) if k == "data"))
        intake = [{"date": "", "text": txt}] if txt else []
    dog["intake_notes"] = intake

    return dog

def main():
    files = sorted(glob.glob(os.path.join(DETAILS_DIR, "*.html")))
    dogs = []
    for f in files:
        aid = os.path.splitext(os.path.basename(f))[0]
        content = open(f, encoding="utf-8", errors="replace").read()
        d = parse_dog(content)
        d["animal_id"] = aid
        d["name"] = d["bio"].get("Name", "")
        dogs.append(d)
    # sort by name
    dogs.sort(key=lambda d: (d.get("name") or "zzz").upper())
    json.dump(dogs, open("dogs_data.json", "w"), indent=2)
    print(f"Parsed {len(dogs)} dogs -> dogs_data.json")
    # quick sanity
    with_eval = sum(1 for d in dogs if d["evaluation_comments"])
    print(f"Dogs with >=1 evaluation comment: {with_eval}")
    print(f"Total evaluation comments: {sum(len(d['evaluation_comments']) for d in dogs)}")

if __name__ == "__main__":
    main()
