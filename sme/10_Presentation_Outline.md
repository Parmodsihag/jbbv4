# Presentation outline (PPT + Q&A)

**The story:** the shop's everyday problems, and how each one is solved. The audience should
leave remembering eight problems and eight answers, then see that the answers are engineered
and tested properly. The talk follows the same order as the problem-first video
(`video/out/high-table-holdings-problems.mp4`), so the video can stand in for the demo.

15 slides, about 11 minutes, then Q&A. Every member presents.

## Design

* **Look:** dark navy background, teal accent (#22D3EE), white headings, Segoe UI. Each
  problem is one slide: the problem in the owner's words, the same line in Hindi under it,
  "How we solved it" chips, and one large screenshot.
* **Ready-made slides:** the video tool draws every slide below at 1920×1080. Run
  `python sme/video/make_video.py slides` and drop the PNGs from `sme/video/out/slides/` into
  PowerPoint as full-slide pictures (`p_title`, `p_shop`, `p_problems`, `p_card_1` … `p_card_8`,
  `p_how`, `p_quality`, `p_end`).
* **Screenshots:** `docs/screenshots/*.png` (light and dark, made-up demo shop), plus the app
  frames in `sme/video/out/frames/` for screens not in the README (crop lots, GST bill, audit
  log, lock screen).
* One idea per slide; at most six words a line. The details are in the speaker notes below and
  in the documentation, not on the slide.

## Slides

| # | Slide | On the slide | Say | Speaker | Time |
|---|-------|--------------|-----|---------|------|
| 1 | **Running a shop on credit is hard. We made it simple.** | Title; course; Team No. and names; Git URL; the Today screenshot | "High Table Holdings is the shop computer for an agri-input shop that sells on credit." | M1 | 0:20 |
| 2 | **Sold today, paid after the harvest** (`p_shop`) | उधार, करार, फ़सल; one owner, one helper, one PC, patchy internet | Farmers take seed and fertiliser now and pay after the harvest; many sell their wheat back. The owner keeps every account and chases every promise, mostly by hand. | M1 | 0:40 |
| 3 | **Eight everyday problems** (`p_problems`) | The eight, in English and Hindi | "Each of the next eight slides is one problem and how we solved it." | M1 | 0:30 |
| 4 | **1 · Who owes me what, exactly, with interest?** | Khata page: *Owes us* split into entered + interest; Statement button | 24 % a year as a daily rate, added to the amount each 31 March. Worked out to the paisa every day, never by hand; a printed statement settles arguments. | M1 | 0:45 |
| 5 | **2 · Promises to pay get forgotten** | Today's *Promises due*; Collections with the reminder and WhatsApp | Late, today, next 7 days, later. The reminder is already written, in English or Hindi; *Got payment* / *New date* records what happened. | M2 | 0:45 |
| 6 | **3 · A busy counter, and mistakes** | Counter: Sale tab, three lines, *Paid now* 2000 cash, the "saved" toast | Shop words instead of debit and credit. Several items and a part payment in one save: account, stock and cash book together or not at all. Ctrl+Z undoes a mistake for 15 minutes. | M2 | 0:50 |
| 7 | **4 · Stock runs out, or expires** | Stock item page: *Lasts about 8 days*; Today's *Stock running out* | Days left at the current selling rate, a reorder list, expiry warnings. Loose sales (500 G of a KG bag) are converted to the stock unit. | M2 | 0:40 |
| 8 | **5 · Crops from farmers: what did we earn?** | Purchase of a wheat lot with kaat and net weight; a sale with "cost from 2 lots · margin" | Each purchase is a lot, with the deduction weighed off. A sale is costed from the oldest lots first, and the margin shows before saving. | M3 | 0:45 |
| 9 | **6 · Where did the money go?** | Money: cash, bank and UPI tiles, cash book; a GST bill with CGST/SGST | One cash book for cash, bank and UPI; expenses and rent; profit and loss. GST invoices with tax by item type and the amount in Hindi words. | M3 | 0:45 |
| 10 | **7 · Not everyone is at home with computers, or English** | Counter in Hindi; the Assistant answering *sabse bade 5 bakayedar* in Hindi | One switch puts every screen, statement and slip into Hindi, names included. Ask in Hindi, Hinglish or English, typed or spoken; it asks back when a name is ambiguous and reads the answer aloud. Offline, and it only reads. | M3 | 0:55 |
| 11 | **8 · Can I trust the records, and keep them safe?** | Audit log (who did what); lock screen; Backup & data settings | Staff can sell but not change history; every change records who made it; the screen locks; daily backups, checked restores, and updates that can be undone. | M4 | 0:50 |
| 12 | **Simple to run, safe to trust** (`p_how`) | Six tiles: own PC, one data file, owner and staff, English or हिन्दी, updates itself, 34 reports | Nothing to install on a server, nothing leaves the shop. | M4 | 0:30 |
| 13 | **How we built it** | Process strip: requirements → specifications → design → build → test → release; artefact chips | Iterative and incremental, test-first for the money rules. Problems became user stories, then numbered requirements; the rules were pinned down with decision tables and algebraic specifications; the design keeps screens, rules and data apart; every major choice is a decision record. | M4 | 1:00 |
| 14 | **Proving it works** (`p_quality`) | 316 automated tests, all passing; traceability excerpt; acceptance checklist | Every requirement traces to test cases; the interest rule is checked against hand-worked figures; a save is tested to be all or nothing; a fresh clone installs and passes on its own. | M4 | 0:45 |
| 15 | **Demo, and fewer problems at the counter** (`p_end`) | 60-second live demo (or the video); what's next; Git URL; thank you | Demo: a sale with a part payment, undo, then a spoken question. Next: recording entries by voice with a confirmation, a market-rate feed, automatic CI. | M1 | 1:00 |

**Total ≈ 11:00.** Rehearse with a timer; slides 4–11 are where time slips, so keep each to its
three points.

### The engineering behind each problem

Keep this table in the speaker notes (or as a backup slide after slide 13); it answers "where is
that in your documentation?" on the spot.

| Problem | Requirements (Ch. 1) | Decision tables (Ch. 3) | Algebraic spec (Ch. 4) | Test cases (Ch. 6) |
|---|---|---|---|---|
| 1 Who owes what | FR-2.3 balance, FR-2.4 interest, FR-2.5 settlement, FR-2.9 statement | DT-5, DT-6, DT-7 | INTEREST, LEDGER | TC-01–16, TC-60 |
| 2 Forgotten promises | FR-5.1–5.4, FR-9.8 | DT-8 | KRAR | TC-49, TC-62–63, TC-96, TC-150–151 |
| 3 Busy counter | FR-4.1–4.5, FR-9.1–9.3, FR-14.2 | DT-2, DT-3, DT-16 | ENTRY | TC-22–30, TC-83–86, TC-148 |
| 4 Stock | FR-3.1–3.6, FR-9.7, FR-9.8 | DT-9, DT-10 | STOCK | TC-20–38, TC-94 |
| 5 Crops | FR-4.4, FR-8.2 | DT-4 | CROPFIFO | TC-39–48, TC-149 |
| 6 Money | FR-8.1, FR-8.3 | DT-12, DT-13 | CASHBOOK | TC-71–80, TC-95 |
| 7 Language | FR-10.1–10.4, FR-11.1–11.7, FR-12.1–12.4 | DT-17, DT-21 | — | TC-108–133 |
| 8 Trust and safety | FR-1.1–1.5, FR-7.1–7.2, FR-9.4–9.6, FR-13.1–13.5 | DT-1, DT-14, DT-15, DT-18, DT-19 | PERMISSIONS, AUDIT, LOCKOUT, UPDATE | TC-51–53, TC-64, TC-87–90, TC-134–144 |

Also ready if asked: the DFDs and ER diagram (Ch. 2), WBS / activity network / PERT and
plan vs actual (Ch. 5), the project management plan (Ch. 7), and `v5/docs/` (architecture,
decision records, test plan, test report).

## Likely Q&A and prepared answers

| Question | Answer |
|----------|--------|
| Why a desktop program, not a website or a phone app? | One shop PC, unreliable internet, and the owner wants the books to stay in the shop. A desktop program with one data file works offline and installs by copying a folder. The business rules have no screen code in them, so a phone or WhatsApp front-end can be added later. |
| How do you know the interest is right? | It is computed in exactly one function and pinned by tests: hand-worked figures (one year at 24 %, compounding across 31 March) and a comparison with the formula the shop already trusted, on random inputs. The owner also compares known customers during acceptance. |
| What happens if the power goes off in the middle of a sale? | A save is one database transaction: the lines, the payment, the stock and the cash book are written together or not at all. A test breaks a save half-way and checks that nothing was written. |
| Can a staff member hide a mistake or steal? | Staff cannot edit or delete history; only the owner can, and every change, delete and sign-in is recorded with the user's name. Repeated wrong passwords make that user wait; the screen locks itself. |
| What if the PC dies? | A backup is taken every day automatically, and one before any upgrade or restore. We advise copying the newest backup off the PC weekly; then at most a week is at risk, and any of the last 14 days can be restored. |
| How do you stop the assistant giving a wrong answer? | It never writes numbers: it picks one of 25 read-only queries that the reports already use. Names are matched only against the shop's own customers and asked back when two match. The optional language model is trusted only when it agrees with one of the classifier's top three guesses (DT-17). |
| Does voice work in a noisy shop? | On 150 spoken test questions with shop-like noise, 95 % were answered right; recognition is limited to the shop's own words. A USB or headset microphone helps most, and typing always works. |
| How does Hindi work without breaking the data? | Only what is shown is translated; the records stay in English, so switching back loses nothing. Each name also gets a stored Hindi copy that can be corrected by hand. |
| How are updates safe? | Only changed files are downloaded, each checked against GitHub's hash; they are put in before the program loads, the old files are kept, and anything that fails is rolled back. *Undo last update* restores the previous files. The shop's data is never touched. |
| How did you plan and track the work? | WBS, activity network and PERT at the start (critical path 57 working days); tracked against actual dates; scope changes went through change control; the remaining work was re-planned with PERT (8.3 days expected, 97 % by 5 Nov against an 11 Nov deadline). |
| How did you test it? | Risk-based test plan; 316 automated tests at unit, integration, migration and UI level; a traceability matrix from every requirement to test cases; an acceptance checklist the owner runs on the shop PC. |
| Why does the repository have `v4/` and `v5/` folders? | The program was built in increments; the earlier build is kept for reference. Everything shown today is in `v5/`. |
| What would you build next? | Recording entries by voice with a confirmation step, a daily market-rate feed for crops, a separate phone-number field, and continuous integration on GitHub. |
| Who did what? | Refer to the first page of the documentation (team and contributions). |
