# fixtures/public/

Documents published by a regulator, kept because a synthetic fixture cannot be wrong in the
ways a real one is.

**Why this exists.** Every other fixture in this repository is synthetic, and synthetic
documents are written by whoever wrote the code that reads them - so they agree with it. The
first time the Document Reader met a real financial statement it took the wrong column of a
comparative balance sheet: `Cash and cash equivalents $ 95,635 $ 171,324` gave the prior
year, with the current year swallowed into the label. That is B-030, predicted in the
backlog and never demonstrated until a real filing was put in front of it.

**Why it is not client data.** These are documents the SEC publishes, filed by public
companies for anyone to read. The rule the repository has always had is that no client data
enters it; masked and synthetic were the two ways to satisfy that rule when it was written,
and a public filing is a third. Nothing here is masked, because there is nothing to mask.

**What belongs here.** A document that is (a) published by a regulator or by the filer
itself for public reading, (b) fetched from that source, and (c) recorded below with where
it came from and when. Nothing a client sent this firm, ever - that is what `knowledge/` is
for, and `interview.py scan` checks the difference on every session.

## What is here

### `sec-ars-3d-systems-2025.pdf`

| | |
|---|---|
| Source | https://www.sec.gov/Archives/edgar/data/910638/000119312526146304/d923469dars.pdf |
| Filer | 3D SYSTEMS CORP (CIK 910638) |
| Form | ARS - Annual Report to Shareholders |
| Accession | 0001193125-26-146304, filed 2026-04-08 |
| Retrieved | 2026-09-19 |
| Size | 589,928 bytes, 108 pages |

Found through EDGAR's quarterly form index rather than picked: ARS filings are the form
type that most often arrives as a PDF rather than as HTML, which is why this is one.

**What it is good for.** Comparative statements on pages 56-58 - a balance sheet with two
year columns and an income statement with three. Two genuinely image-only pages, 107 and
108, which is a real scanned page rather than one manufactured for a test. A hundred pages
of ordinary prose and tables around them, which is what the table recovery has to not
choke on.
