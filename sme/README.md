# SEM 2026-27 — Software Engineering & Management project pack

Course project deliverables for **High Table Holdings v4** (accounting & inventory
management for an agri-input shop), prepared against the official *Project Guidelines*
(`SEM202627_ProjectGuidelines.pdf`).

| # | File | Guideline item it satisfies |
|---|------|-----------------------------|
| 1 | [01_Abstract.md](01_Abstract.md) | §2–4 — 1-page abstract with conceptual diagram, team number and members. Export to `TeamNo.pdf`. |
| 2 | [02_Team_and_Contributions.md](02_Team_and_Contributions.md) | §8 — first page of the documentation: members, contributions, Git URL. |
| 3 | [03_SRS.md](03_SRS.md) | §8 — informal specification (user stories, glossary), semi-formal specification (use cases, activity / sequence / state diagrams) and formal SRS (IEEE 830 structure, FR/NFR ids, pre/post-conditions). |
| 4 | [04_DFD_and_Data_Model.md](04_DFD_and_Data_Model.md) | §8 — DFD modelling (context, level 1, level 2), ER diagram, architecture. |
| 5 | [05_Decision_Tables.md](05_Decision_Tables.md) | §8 — formal specification: decision tables. |
| 6 | [06_Algebraic_Specifications.md](06_Algebraic_Specifications.md) | §8 — formal specification: algebraic specifications of the core ADTs. |
| 7 | [07_WBS_Activity_Network_PERT.md](07_WBS_Activity_Network_PERT.md) | §8 — Work Breakdown Structure, Activity Network (CPM), PERT chart, Gantt. |
| 8 | [08_Test_Cases.md](08_Test_Cases.md) | §8 — test cases for the working prototype + traceability matrix. |
| 9 | [09_Video_Script.md](09_Video_Script.md) | §7 — 2–3 minute screencast script (compile, deploy, features). |
| 10 | [10_Presentation_Outline.md](10_Presentation_Outline.md) | §5d — PPT outline and likely Q&A. |
| — | [build_docs.sh](build_docs.sh) | Concatenates 02…08 into `Documentation.md` and, when `pandoc` is installed, renders `Documentation.pdf`. |

## Before submitting

1. Fill in **Team No.** and the four member names / BITS IDs in `01_Abstract.md` and
   `02_Team_and_Contributions.md` (search for `<<` placeholders).
2. Make the Git repository **public** and confirm the URL in `02_Team_and_Contributions.md`
   (currently `https://github.com/Parmodsihag/jbbv4`).
3. Abstract → export `01_Abstract.md` as **`TeamNo.pdf`** (e.g. `Team05.pdf`).
4. Final → run `./build_docs.sh`, put `Documentation.pdf` and the video in **`TeamNo.zip`**.

## Rendering diagrams

All diagrams are Mermaid blocks, which GitHub renders natively. For PDF:

* **VS Code**: install *Markdown Preview Enhanced* → right-click preview → *Export → PDF*.
* **pandoc**: `brew install pandoc` and `npm i -g @mermaid-js/mermaid-cli mermaid-filter`,
  then `./build_docs.sh`.
* **Online**: paste any block into <https://mermaid.live> and export PNG if a tool cannot render it.

## Deadlines (from the guidelines)

| Item | Deadline |
|------|----------|
| Abstract (`TeamNo.pdf` on Nalanda) | 25 Aug, 11:55 PM |
| Final submission (`TeamNo.zip`: video + documentation; public Git repo) | 11 Nov, 11:55 PM |
| PPT + Q&A | as scheduled by the instructor |
| Grades | by 25 Nov (team-based, relative) |
