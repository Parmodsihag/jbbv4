# SEM 2026-27 — Software Engineering & Management project pack

Course project deliverables for **High Table Holdings** (accounting & inventory management
for an agri-input shop), prepared against the official *Project Guidelines*
(`v5/SEM202627_ProjectGuidelines_….pdf`). The pack documents the working prototype as of
**version 5.7.0** (folder `v5/`); v4 was the first increment.

| # | File | Guideline item it satisfies |
|---|------|-----------------------------|
| 1 | [01_Abstract.md](01_Abstract.md) | §2–4 — 1-page abstract with conceptual diagram, team number and members (`TeamNo.pdf`). Written for the v4 scope at the start of the course and kept as submitted. |
| 2 | [02_Team_and_Contributions.md](02_Team_and_Contributions.md) | §8 — first page of the documentation: members, contributions, Git URL. |
| 3 | [03_SRS.md](03_SRS.md) | §8 — informal specification (user stories, glossary), semi-formal (use cases, activity / sequence / state diagrams) and formal SRS (IEEE 830 structure, FR/NFR ids, pre/post-conditions); v5 requirements FR-9 – FR-14. |
| 4 | [04_DFD_and_Data_Model.md](04_DFD_and_Data_Model.md) | §8 — DFD modelling (context, level 1, level 2), ER diagram, architecture, deployment. |
| 5 | [05_Decision_Tables.md](05_Decision_Tables.md) | §8 — formal specification: decision tables DT-1 – DT-22. |
| 6 | [06_Algebraic_Specifications.md](06_Algebraic_Specifications.md) | §8 — formal specification: algebraic specifications of the core ADTs. |
| 7 | [07_WBS_Activity_Network_PERT.md](07_WBS_Activity_Network_PERT.md) | §8 — Work Breakdown Structure, Activity Network (CPM), PERT chart, Gantt; plan vs actual; re-baselined plan to submission. |
| 8 | [08_Test_Cases.md](08_Test_Cases.md) | §8 — test cases for the working prototype (TC-1 – TC-166), traceability matrix, acceptance checklist. |
| 9 | [11_Project_Management.md](11_Project_Management.md) | Management practice: charter, process model, RACI, communication, configuration and change management, quality, metrics, lessons learned. |
| 10 | [09_Video_Script.md](09_Video_Script.md) | §7 — 2–3 minute screencast script (compile, deploy, features). |
| 11 | [10_Presentation_Outline.md](10_Presentation_Outline.md) | §5d — PPT outline and likely Q&A. |
| — | [build_docs.sh](build_docs.sh) | Concatenates 02…08 and 11 into `Documentation.md` and, when `pandoc` is installed, renders `Documentation.pdf`. |

Engineering documents that support the pack live with the code in
[`v5/docs/`](../v5/docs/README.md): user guide, admin guide, architecture, decision records,
data dictionary, test plan and the 5.7.0 test report.

## Before submitting

1. Fill in **Team No.** and the four member names / BITS IDs in `01_Abstract.md` and
   `02_Team_and_Contributions.md` (search for `<<` placeholders), and correct the
   contributions table so it shows who did what.
2. Fill in the actual date of M0 in `07_WBS_Activity_Network_PERT.md` §5.8 (`*fill in*`).
3. Confirm the Git repository is **public**: <https://github.com/Parmodsihag/jbbv4>.
4. Final → run `./build_docs.sh`, check the PDF (diagrams render, tables fit), put
   `Documentation.pdf` and the video in **`TeamNo.zip`**.

## Rendering diagrams

All diagrams are Mermaid blocks, which GitHub renders natively. For PDF:

* **VS Code**: install *Markdown Preview Enhanced* → right-click preview → *Export → PDF*.
* **pandoc**: install pandoc and `npm i -g @mermaid-js/mermaid-cli mermaid-filter`, then
  `./build_docs.sh` (from Git Bash on Windows).
* **Online**: paste any block into <https://mermaid.live> and export PNG if a tool cannot render it.

## Deadlines (from the guidelines)

| Item | Deadline |
|------|----------|
| Abstract (`TeamNo.pdf` on Nalanda) | 25 Aug, 11:55 PM |
| Final submission (`TeamNo.zip`: video + documentation; public Git repo) | 11 Nov, 11:55 PM (team target: 5 Nov, see §5.10) |
| PPT + Q&A | as scheduled by the instructor |
| Grades | by 25 Nov (team-based, relative) |
