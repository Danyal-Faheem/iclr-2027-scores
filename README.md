# ICLR 2027 Scores

Score distributions and a paper list for ICLR 2027 submissions, updated with snapshots during the discussion period.

The page shows paper titles, numeric scores and OpenReview links only. Raw downloads contain review text, stay in `snapshots/` and `notes/`, and are never committed.

## Setup

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Take a snapshot

```sh
.venv/bin/python download.py      # one paginated pass over all submissions and reviews
.venv/bin/python build_site.py    # writes docs/data/ from snapshots/
git add docs && git commit -m "Add snapshot" && git push
```

`download.py` makes about one API request per 1000 submissions, with no per-paper requests. Each page is saved as it arrives. If a run stops, running it again continues from the next page. Use `--new` to abandon an unfinished run.

The OpenReview client uses `OPENREVIEW_USERNAME` and `OPENREVIEW_PASSWORD` if they are set in the environment. OpenReview may refuse anonymous API requests with a `ChallengeRequiredError`. The script then stops, prints the response, and keeps its progress.

If you saved the API pages by hand instead, put them in `notes/` (git-ignored) and run `.venv/bin/python import_notes.py` in place of `download.py`. It refuses to import if a file is duplicated or any submission is missing.

`build_site.py` uses only snapshots whose `manifest.json` says `"complete": true`. Each snapshot leaves a numeric summary in `docs/data/snapshots/`, so the history survives if raw snapshots are deleted, except that the newest raw snapshot is needed to rebuild the paper list.

## What the page counts

- Withdrawn and desk-rejected submissions are left out of the charts and list. Their counts appear in the footer.
- Only official reviews count. Ratings in other replies are ignored.
- Rank is by mean rating, and tied papers share a rank.
- The Change column compares each paper's mean rating with the first snapshot.

## Tests

```sh
.venv/bin/python tests/test_pipeline.py
```

The tests use synthetic data and make no network calls.
