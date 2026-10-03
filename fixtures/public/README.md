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

### `sec-ars-resmed-2026.pdf`

| | |
|---|---|
| Source | https://www.sec.gov/Archives/edgar/data/943819/000094381926000084/rmd-20260630xasfiledaugust.pdf |
| Filer | ResMed Inc. (CIK 943819) |
| Form | ARS - Annual Report to Shareholders |
| Accession | 0000943819-26-000084, filed 2026-10-01 |
| Retrieved | 2026-10-03 |
| Size | 1,102,528 bytes, 124 pages |
| SHA-256 | `1d42a619755cee796caa605c2d420bc1d03e1863d1aaae3e5f1e6ddc98bbddc2` |

**Why a second PDF.** One filing is one typesetter's idea of a balance sheet, and the reader
has been fixed until it read the first one - which is how it should be and is also why that
one's score says less than it looks. This one had never been read by anything here, so it is
the first honest accuracy number in the build.

A different shape in several ways that matter: a fiscal year ending 30 June rather than 31
December, a balance sheet of 70 figures over two columns where the other has 61, and a scale
line that states its own exception - *(In US$ and in thousands, except share and per share
data)*, which is the filing saying out loud that some of its figures are not at its stated
scale.

**What it found.** Nothing wrong, which is the result worth having from an unseen document:
all 70 figures matched a figure the filer tagged at that column's own date, both columns
balance, and all eight footings re-add. Checked by `tools/check_against_filer.py`.

### `sec-financial-report-3d-systems-2025q1.xlsx`

| | |
|---|---|
| Source | https://www.sec.gov/Archives/edgar/data/910638/000091063825000010/Financial_Report.xlsx |
| Filer | 3D SYSTEMS CORP (CIK 910638) |
| Form | the Excel export EDGAR generates from a filing's XBRL - here the 10-Q for the quarter ended 2025-03-31 |
| Accession | 0000910638-25-000010 |
| Retrieved | 2026-10-03 |
| Size | 92,696 bytes, 66 sheets |
| SHA-256 | `a9f520aa5a30d1eccd7d7298a7dd2650ea1e210f2291dc43e0179648120f3bf3` |

**Why a workbook nobody here wrote.** Every other `.xlsx` in `fixtures/` was written by
openpyxl by whoever wrote the code that reads it, so it agrees with that code by
construction. This one was laid out by the regulator from the filer's own tags: sheet names
truncated to 31 characters with `_2` suffixes, a non-breaking space where a cell is blank, a
header row that states the units (`USD ($) $ in Thousands`), and share counts as their own
rows beside dollar figures.

**What it found.** The scale, currency and period type all read correctly, 63 of its 68
balance-sheet figures matched a fact at the right date and none at a wrong one - and the
thing one document could not have shown: a **share count is its own row here**, where a PDF
keeps it inside the label. `Common stock, shares, issued (in shares)` is 135,361,000 in the
cell while every dollar figure on the sheet is in thousands, so applying the statement's
scale to it reports 135 billion shares and turns a par value of $0.001 into $1.00. That is
B-131.

### `filer-facts/`

The filer's own figures, as tagged in XBRL and served by
`https://data.sec.gov/api/xbrl/companyfacts/`, trimmed to the dates each filing's statements
are as of. Ground truth for `tools/check_against_filer.py`.

**Committed rather than fetched** because this build is local-only and its tests run offline:
a tool that needed `data.sec.gov` to answer would answer differently on a train, and a test
that needed it would fail for a reason that is not about the code. `--fetch` is the one
networked path and it is an explicit act.

Each file records its source, the accession it belongs to, when it was retrieved, and what
the comparison **cannot** see - `companyfacts` serves the dimensionless facts, so a figure
tagged only against a segment or a share class is in the filing's own XBRL and not here.
