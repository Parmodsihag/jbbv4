# Documentation

Everything written about High Table Holdings v5, by who needs it. Version documented:
**5.7.0**.

## Using the program

| document | for | what is in it |
|---|---|---|
| [USER_GUIDE.md](USER_GUIDE.md) | shop owner and staff | every everyday task in the New layout, shortcuts, who can do what, how the numbers work |
| [../README.md](../README.md) | everyone | the v5 manual: Classic screens, modules, reports, business rules, Hindi, the Assistant |
| [../CHANGELOG.md](../CHANGELOG.md) | everyone | what changed in each version |

## Running it

| document | for | what is in it |
|---|---|---|
| [ADMIN_GUIDE.md](ADMIN_GUIDE.md) | the admin, whoever installs it | install, first start, the data folder, backups and restore, updates, users, troubleshooting, routine checklist |
| [../../SECURITY.md](../../SECURITY.md) | admin, developers | what is protected and what is not; reporting a problem |

## Building and changing it

| document | for | what is in it |
|---|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | developers, reviewers | goals, context, layers, runtime flows, cross-cutting concepts, deployment, quality scenarios, technical debt |
| [adr/](adr/README.md) | developers, reviewers | 13 architecture decision records: why it is built this way |
| [DATA_DICTIONARY.md](DATA_DICTIONARY.md) | developers | every table and column, migrations, settings keys, codes |
| [AI_CHAT_DESIGN.md](AI_CHAT_DESIGN.md) | developers | the Assistant's design: System 1 / System 2, tools, training, evaluation |
| [VOICE_DESIGN.md](VOICE_DESIGN.md) | developers | asking by voice: recogniser, vocabulary, spoken answers, measurements |
| [../hth/modules/README.md](../hth/modules/README.md) | developers | how to write a feature module |
| [../../CONTRIBUTING.md](../../CONTRIBUTING.md) | developers | set-up, workflow, code standards, how-tos, definition of done |
| [RELEASING.md](RELEASING.md) | maintainer | versions, branches, release checklist, rollback, hotfixes, CI |

## Testing it

| document | for | what is in it |
|---|---|---|
| [TEST_PLAN.md](TEST_PLAN.md) | testers, developers | risks, levels, techniques, the 26 suites, criteria, defect management |
| [TEST_REPORT_5.7.0.md](TEST_REPORT_5.7.0.md) | team, reviewers | results of the 5.7.0 run: 316 of 316 passed |

## The course pack

[`../../sme/`](../../sme/README.md) holds the Software Engineering & Management (SEM 2026-27)
deliverables for this project: SRS (informal, semi-formal, formal), DFDs and data model,
decision tables, algebraic specifications, WBS / activity network / PERT / Gantt, test cases
with traceability, project management plan, video script and presentation outline.

## Keeping these right

* The code is the source of truth. When a document and the code disagree, fix the document
  in the same pull request ([CONTRIBUTING.md › Documentation](../../CONTRIBUTING.md#documentation)).
* Each test report is for one version and is not edited afterwards; the next release gets a
  new one.
* Decision records are never rewritten; a new one supersedes an old one.
