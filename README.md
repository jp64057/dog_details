# dog_details

Scraping toolkit for the public **Maricopa County Animal Care & Control**
adoptable-dogs listing (`https://apps.pets.maricopa.gov/adoptPets/`). It collects
every adoptable dog's Animal ID, downloads each dog's full detail page, parses the
data into structured JSON, and renders human-readable reports — including each
dog's dated **evaluation comments**.

Everything is **Python standard library only** — no `pip install` required
(Python 3.9+).

> **Data is not tracked in this repo.** `.gitignore` excludes all scraped and
> generated output (`*.txt`, `*.json`, `*.md`) and the raw HTML cache
> (`details/`). Only the source scripts are shared. Run the pipeline yourself to
> produce the data locally.

## Pipeline

```
collect_animal_ids.py  ->  all_ids.txt          # collect every adoptable dog's Animal ID
fetch_details.py       ->  details/*.html        # download each dog's detail page (photos stripped)
parse_dogs.py          ->  dogs_data.json        # parse detail pages into structured records
build_outputs.py       ->  dogs_full_details.md  # render full report
                           evaluation_notes.txt  # render evaluation comments only
```

Run it end to end:

```bash
python3 collect_animal_ids.py
python3 fetch_details.py
python3 parse_dogs.py
python3 build_outputs.py
```

## Scripts

### `collect_animal_ids.py`
Pages the public `AnimalGrid` endpoint, extracts every
`ShowDetailsForAnimal('<AnimalID>')` reference, de-duplicates, and writes the IDs
one per line. Re-runnable — run it again anytime to refresh the list.

```bash
python3 collect_animal_ids.py                       # -> all_ids.txt
python3 collect_animal_ids.py --output ids.txt      # custom output (use '-' for stdout)
python3 collect_animal_ids.py --animal-type Dog --max-pages 50
```

Options: `--output/-o`, `--animal-type`, `--max-pages`, `--delay`, `--timeout`.

### `fetch_details.py`
Reads the ID list and downloads each animal's `/Home/Details/<id>` page into a
local cache directory, stripping the large inline base64 photos so cached files
stay small. Concurrent and re-runnable — already-downloaded IDs are skipped
unless `--force` is given.

```bash
python3 fetch_details.py                             # all_ids.txt -> details/
python3 fetch_details.py --input ids.txt --out-dir details --workers 8
python3 fetch_details.py --force                     # re-download everything
```

Options: `--input/-i`, `--out-dir/-d`, `--workers`, `--timeout`, `--retries`, `--force`.

### `parse_dogs.py`
Parses every cached detail page in `details/` into `dogs_data.json`. Each record
includes the bio fields (name, breed, age, sex, weight, adoption fee, arrival
date, location, level), the "About me" blurb, requirements, recommendations, and
the dated **evaluation comments**, intake notes, and medical treatments.

```bash
python3 parse_dogs.py                                # details/*.html -> dogs_data.json
```

### `build_outputs.py`
Renders two reports from `dogs_data.json`:

- **`dogs_full_details.md`** — every field for every dog.
- **`evaluation_notes.txt`** — an "Evaluation Notes" section with each dog's dated
  evaluation comments.

```bash
python3 build_outputs.py
```

## Notes

- The grid header reports a total "Found" count that can exceed the number of
  dogs actually rendered as cards; some animals are not publicly listed and
  therefore can't be collected this way. The collector logs the difference.
- Please scrape responsibly — the defaults include a small inter-request delay
  and modest concurrency. Adjust `--delay` / `--workers` to be gentle on the
  source site.
