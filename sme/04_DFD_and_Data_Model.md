# Chapter 2 — DFD modelling, data model and architecture

Notation (Gane–Sarson mapped to Mermaid): **rectangles** = external entities, **rounded
/ circles** = processes, **cylinders** = data stores, arrows = data flows.

## 2.1 Context diagram (DFD level 0)

```mermaid
flowchart LR
  ADM[Administrator]
  EMP[Employee]
  CUST[Customer / Farmer / Buyer]
  V3[(Legacy v3 files)]
  V4[(v4 database<br/>read only)]
  GH[GitHub<br/>update channel]
  P0((0<br/>High Table<br/>Holdings v5))
  FILES[Excel, HTML statement, DOCX/PDF invoice, slip, Backup]

  ADM -- "credentials, entries, corrections,<br/>user & settings changes, import / restore /<br/>update requests" --> P0
  EMP -- "credentials, sales / receipts,<br/>new accounts & items, krar,<br/>typed or spoken questions" --> P0
  P0 -- "Today, ledgers, reports,<br/>alerts, audit log, answers" --> ADM
  P0 -- "balances, today's entries,<br/>reminder text, answers (shown / spoken)" --> EMP
  P0 -- "statement, invoice, slip, WhatsApp reminder" --> CUST
  V3 -- "customers, ledgers, items, krar, notes" --> P0
  V4 -- "hth.db (first start)" --> P0
  GH -- "version, changelog, changed files + hashes" --> P0
  P0 -- "exports, backups" --> FILES
```

The only flow that leaves the PC is the request to GitHub for the version and files; no
shop data is sent.

## 2.2 DFD level 1

Both roles use the same screens, so they are shown as one external entity *Users*;
flows that only an Administrator can trigger are marked **(admin)**. Process 1 checks the
permission matrix for every other process (DT-1); those control flows are omitted from the
diagram to keep the data flows readable.

```mermaid
flowchart TB
  USR[Users<br/>Employee / Administrator]
  V3[(Legacy v3 files)]
  OUT[Export files]

  P1((1<br/>Authenticate &<br/>authorise))
  P2((2<br/>Manage<br/>accounts))
  P3((3<br/>Record<br/>transaction))
  P4((4<br/>Manage<br/>inventory))
  P5((5<br/>Manage<br/>krar))
  P6((6<br/>Report &<br/>dashboard))
  P7((7<br/>Administer<br/>system))
  P8((8<br/>Feature modules<br/>bills, crops, finance))

  D1[(D1 users)]
  D2[(D2 customers)]
  D3[(D3 transactions)]
  D4[(D4 items)]
  D5[(D5 item_transactions)]
  D6[(D6 krar / krar_dates)]
  D7[(D7 audit_log)]
  D8[(D8 settings)]
  D9[(D9 module tables)]

  USR -- credentials --> P1
  P1 <-- user record --> D1
  P1 -- login event --> D7
  P1 -- session --> USR

  USR -- customer details --> P2
  P2 -- customer --> D2
  P2 -- opening balance --> D3
  P2 -- "01 / 05 / 06" --> D7

  USR -- sale / receipt form --> P3
  D2 -- account --> P3
  D4 -- item, last price --> P3
  P3 -- ledger rows --> D3
  P3 -- stock movement --> D5
  P3 -- last price --> D4
  P3 -- crop lot / cash-book row --> P8
  P3 -- "03 / 04" --> D7
  P3 -- balance preview, result --> USR

  USR -- item details --> P4
  P4 -- item --> D4
  P4 -- opening stock --> D5
  P4 -- "02 / 05 / 06" --> D7

  USR -- promise date / settle --> P5
  D3 -- balance --> P5
  P5 -- krar, dates --> D6
  P5 -- "07" --> D7
  P5 -- reminder text --> USR

  D2 & D3 & D4 & D5 & D6 -- rows --> P6
  D7 & D8 & D9 -- rows --> P6
  P6 -- reports, KPIs --> USR
  P6 -- xlsx / html --> OUT

  USR -- "users, settings, backup, import (admin)" --> P7
  V3 -- v3 tables --> P7
  P7 <-- users, settings --> D1 & D8
  P7 -- migrated rows --> D2 & D3 & D4 & D5 & D6
  P7 -- "08 / 09, v3 notes" --> D7
  P7 -- backup file, migration report --> OUT

  USR -- invoice, crop trade, expense --> P8
  P8 <-- lots, bills, cash book --> D9
  P8 -- ledger rows --> D3
  P8 -- stock rows --> D5
  P8 -- "10 / 11 / 12" --> D7
  P8 -- docx / pdf --> OUT
```

**(v5) Processes added in v5.** The level-1 diagram above is unchanged; v5 adds two
processes beside it.

```mermaid
flowchart TB
  USR[Users]
  GH[GitHub update channel]
  APP[(D10 app files)]
  D2[(D2 customers)]
  D3[(D3 transactions)]
  D4[(D4 items)]
  D5[(D5 item_transactions)]
  D6[(D6 krar)]
  D7[(D7 audit_log)]
  D8[(D8 settings)]
  D9[(D9 module tables)]
  D11[(D11 updates/ staged files, backup zips)]

  P9((9<br/>Answer<br/>question))
  P10((10<br/>Update<br/>program))

  USR -- "question (text / speech)" --> P9
  D2 & D4 -- "names, Hindi copies" --> P9
  D3 & D5 & D6 & D9 -- "rows (read only)" --> P9
  P9 -- "answer card, spoken summary, ask-back" --> USR
  P9 -- "13 tool + arguments" --> D7

  USR -- "check / install / undo (admin)" --> P10
  D8 -- "repo, branch, folder" --> P10
  GH -- "version, changelog, files, hashes" --> P10
  APP -- "local file hashes" --> P10
  P10 -- staged files --> D11
  D11 -- "at next start: new files" --> APP
  APP -- "replaced files" --> D11
  P10 -- "14" --> D7
  P10 -- "new version, notes" --> USR
```

## 2.3 DFD level 2 — Process 3 *Record transaction*

```mermaid
flowchart TB
  U[Employee / Admin]
  D2[(D2 customers)]
  D3[(D3 transactions)]
  D4[(D4 items)]
  D5[(D5 item_transactions)]
  D7[(D7 audit_log)]
  D9a[(D9 crop_lots / crop_sales)]
  D9b[(D9 finance_entries)]

  P31((3.1<br/>Validate<br/>input))
  P32((3.2<br/>Convert unit &<br/>compute amount))
  P33((3.3<br/>Write ledger<br/>entry))
  P34((3.4<br/>Settle<br/>period))
  P35((3.5<br/>Update<br/>stock))
  P36((3.6<br/>Crop lot /<br/>FIFO sale))
  P37((3.7<br/>Cash-book<br/>row))
  P38((3.8<br/>Audit))

  U -- kind, date, account, item, qty, unit, price, tag --> P31
  D2 -- account exists? --> P31
  D4 -- item, unit, last price --> P31
  P31 -- error --> U
  P31 -- valid form --> P32
  P32 -- crop item --> P36
  P32 -- "tag 0" --> P34
  P32 -- "tag 1|2" --> P33
  D3 -- current period --> P34
  P34 -- entry, Settled Amount, Discount --> D3
  P33 -- entry --> D3
  P33 & P34 -- stock item --> P35
  P33 -- money entry + account --> P37
  P35 -- received / sale, value --> D5
  P35 -- last price --> D4
  D9a -- open lots --> P36
  P36 -- lot / sale + allocations --> D9a
  P36 -- ledger row --> D3
  P36 -- stock row --> D5
  P37 --> D9b
  P35 & P36 & P37 --> P38
  P38 -- "03 sale / 04 receive / 10 crop" --> D7
  P38 -- result --> U
```

## 2.4 DFD level 2 — Process 7 *Administer system* (import path)

```mermaid
flowchart LR
  ADM[Administrator]
  V3[(v3 data folder)]
  P71((7.1<br/>Backup<br/>current DB))
  P72((7.2<br/>Read v3<br/>tables))
  P73((7.3<br/>Normalise<br/>tags / types / dates))
  P74((7.4<br/>Write rows,<br/>preserve ids))
  P75((7.5<br/>Migration<br/>report))
  P76((7.6<br/>Data<br/>check))
  BK[(backups/)]
  DB[(hth.db)]
  RPT[migration_report.txt]

  ADM -- folder path --> P71 --> BK
  P71 --> P72
  V3 --> P72 --> P73 --> P74 --> DB
  P73 -- skipped / normalised values --> P75 --> RPT
  P74 --> P76
  DB --> P76 -- findings --> ADM
```

## 2.4a DFD level 2 — Process 9 *Answer question* (v5)

```mermaid
flowchart LR
  U[User]
  MIC[Microphone]
  D2[(D2 customers)]
  D4[(D4 items)]
  DB[(D3 / D5 / D6 / D9<br/>read only)]
  D7[(D7 audit_log)]
  MOD[(assistant/<br/>classifier cache,<br/>optional model)]

  P91((9.1<br/>Recognise<br/>speech))
  P92((9.2<br/>Normalise:<br/>language, period,<br/>numbers))
  P93((9.3<br/>Link names))
  P94((9.4<br/>Classify<br/>intent))
  P95((9.5<br/>Run tool))
  P96((9.6<br/>Compose<br/>answer))

  MIC -- audio --> P91
  D2 & D4 -- Hindi names, villages --> P91
  P91 -- "text as heard" --> P92
  U -- typed question --> P92
  P92 --> P93
  D2 & D4 -- names --> P93
  P93 -- "ambiguous: choices" --> U
  P93 -- "text with C1 / I1" --> P94
  MOD -- weights --> P94
  P94 -- "unsure: did you mean" --> U
  P94 -- "intent + slots" --> P95
  DB -- rows --> P95
  P95 -- "13" --> D7
  P95 -- figures --> P96
  P96 -- "card (+ spoken summary)" --> U
```

## 2.5 Entity-relationship diagram

Schema version 6 (v5). Column names are the real ones in `v5/hth/db/schema.py`; the full
data dictionary with every column is `v5/docs/DATA_DICTIONARY.md`. "(m4)" marks a column
added by migration 4, and so on.

```mermaid
erDiagram
  users {
    int id PK
    text username UK "case-insensitive"
    text full_name
    text role "admin or employee"
    text password_hash "PBKDF2-SHA256"
    text salt
    int is_active
  }
  customers {
    int id PK
    text name
    text other_details
    text category "A-E (m4)"
    int category_locked "(m4)"
    text name_hi "(m6)"
    text details_hi "(m6)"
    int hi_manual "(m6)"
  }
  transactions {
    int id PK
    int customer_id FK
    text date
    text description
    real amount
    text type "P or M"
    text tag "0, 1 or 2"
    int legacy_id
    text created_by
  }
  items {
    int id PK
    text name
    real stock_value "cost per unit"
    real last_value "last price per unit"
    text unit
    text batch
    text expiry_date
    real gst_rate
    text item_type "F P S C O"
    text pakka_kacha
    text category "(m4)"
    text name_hi "(m6)"
  }
  item_transactions {
    int id PK
    int item_id FK
    text date
    real received
    real sale
    real value "(m5)"
    text description
    text created_by
  }
  krar {
    int id PK
    int customer_id FK
    int is_nill
  }
  krar_dates {
    int id PK
    int krar_id FK
    text date
  }
  audit_log {
    int id PK
    text ts
    text date
    text username
    text code "01-14"
    text message
  }
  settings {
    text key PK
    text value
  }
  bills {
    int id PK
    int bill_number UK "FY prefix + serial"
    text date
    int customer_id FK "set null"
    text customer_name
    real taxable
    real cgst
    real sgst
    real grand_total
    text source "manual or batch"
  }
  bill_lines {
    int id PK
    int bill_id FK
    text name
    real rate
    real quantity
    real amount
    real gst_rate
    real cgst
    real sgst
  }
  bill_month_items {
    int id PK
    text month_year
    int item_id
    real quantity
  }
  crop_lots {
    int id PK
    int farmer_id FK "restrict"
    int item_id FK "restrict"
    text date
    real gross_qty
    real deduction_qty "kaat"
    real qty "net"
    real remaining_qty
    real rate
    text quality
    int tx_id
  }
  crop_sales {
    int id PK
    int buyer_id FK "set null"
    int item_id FK "restrict"
    real qty
    real rate
    real cost
    real margin
    real short_qty
    int tx_id
  }
  crop_sale_lots {
    int id PK
    int sale_id FK
    int lot_id FK "set null"
    real qty
    real cost_rate
    real cost
  }
  crop_rates {
    int id PK
    int item_id FK
    text date
    real rate
    text source
  }
  money_accounts {
    int id PK
    text name UK
    text kind "cash bank upi other"
    real opening_balance
    int is_active
  }
  expense_heads {
    int id PK
    text name UK
    text kind "expense or income"
  }
  finance_entries {
    int id PK
    text date
    text kind
    int account_id FK "restrict"
    int counter_account_id FK "restrict"
    int head_id FK "restrict"
    int customer_id FK "set null"
    real amount
    int tx_id "ledger row"
  }
  finance_recurring {
    int id PK
    int head_id FK
    int account_id FK
    real amount
    int day_of_month
    text last_posted
  }

  customers ||--o{ transactions : "ledger"
  customers ||--o{ krar : "promises"
  krar ||--|{ krar_dates : "dates"
  items ||--o{ item_transactions : "moves"
  customers |o--o{ bills : "billed"
  bills ||--|{ bill_lines : "lines"
  items ||--o{ crop_lots : "crop"
  customers ||--o{ crop_lots : "farmer"
  items ||--o{ crop_sales : "crop"
  customers |o--o{ crop_sales : "buyer"
  crop_sales ||--|{ crop_sale_lots : "FIFO"
  crop_lots |o--o{ crop_sale_lots : "allocated"
  items ||--o{ crop_rates : "market"
  money_accounts ||--o{ finance_entries : "book"
  expense_heads |o--o{ finance_entries : "head"
  customers |o--o{ finance_entries : "receipt or payment"
  expense_heads ||--o{ finance_recurring : "template"
  money_accounts ||--o{ finance_recurring : "from"
```

Key integrity rules:

* `CHECK` constraints on `transactions.type`, `transactions.tag`, `users.role`,
  `money_accounts.kind`, `expense_heads.kind`, `finance_entries.kind`.
* Foreign keys are enforced (`PRAGMA foreign_keys = ON`). Deleting a customer **cascades**
  to its ledger rows and promises, deleting an item to its movements and market rates, a
  bill to its lines. Crop lots and sales **restrict** deletion of their farmer and crop (a
  clear message is shown instead), cash-book entries restrict deletion of their money
  account and head, and a bill, crop sale or cash-book entry **sets null** when its
  customer is deleted.
* Plain integer links without a foreign key: `crop_lots.tx_id` / `stock_tx_id`,
  `crop_sales.tx_id` / `stock_tx_id`, `finance_entries.tx_id`, `bill_month_items.item_id`.
* Indexes `ix_tx_customer_date (customer_id, date, id)`, `ix_itx_item_date (item_id, date, id)`,
  `ix_krar_customer (customer_id, is_nill)`, `ix_fin_account_date (account_id, date, id)`
  and others.
* Schema version in `PRAGMA user_version`; migrations 1 (core) → 2 (bills) → 3 (crops)
  → 4 (categories) → 5 (finance) → 6 (Hindi names, v5).

## 2.6 Architecture

```mermaid
flowchart TB
  subgraph UI ["hth/ui - presentation (customtkinter)"]
    APP[app.py: window, sign-in, lock, layout switch, shortcuts]
    MODERN["modern/ (v5.5): New layout - Today, Counter, Khata, Stock, Money, Reports, Settings"]
    VIEWS[views/: Classic screens - dashboard, sales, customers, items, karar, reports, settings, users, assistant]
    WID[widgets: datatable, searchbox, forms, dialogs, kpi, charts, theme picker, Hindi review]
    CTX[AppContext: db, services, user, can, navigate, toast]
  end
  subgraph MODS ["hth/modules - optional features"]
    BILLS[bills]
    CROPS[crop_trading]
    FIN[finance]
  end
  subgraph ASST ["hth/assistant (v5) - no Tk"]
    CORE[core: pipeline, ask-back]
    S1[normalize, entities, system1]
    S2[system2: own process, optional]
    TOOLS[tools: 25 read-only answers]
    VOICE[voice, speech, spoken]
  end
  subgraph SVC ["hth/services - business logic (no Tk)"]
    ACC[accounts] --- SAL[sales] --- INV[inventory]
    KR[krar] --- REP[reports] --- INS[insights]
    AUTH[auth] --- PERM[permissions] --- AUD[audit]
    BKP[backup] --- UPD[updates] --- INTG[integrity]
    STM[statements] --- SLP[slips] --- REM[reminders] --- SRCH[search] --- EXP[export]
    SET[settings] --- PREF[preferences] --- CAT[categories] --- HIN[hindi]
  end
  subgraph I18N ["hth/i18n (v5)"]
    TR[tr, hi.py phrase table, widget hook, translit]
  end
  subgraph DOM ["hth/domain - pure rules (no I/O)"]
    INT[interest.py]
    UNITS[units.py]
    NUM[numbers.py]
    CONST[constants.py, models.py]
  end
  subgraph DB ["hth/db"]
    CONN[connection.py: transaction-scoped, re-entrant, kept per thread, version counter]
    SCHEMA[schema.py: versioned atomic migrations]
  end
  MIG[hth/migration/from_v3.py]
  TOOLS2[tools/: migrate_v3, check_data, readme_shots, assistant eval]

  APP --> MODERN & VIEWS --> WID
  MODERN & VIEWS --> CTX --> SVC
  MODERN & VIEWS --> MODS --> SVC
  MODERN & VIEWS --> ASST --> SVC
  MODS -. register handlers .-> SAL
  UI --> I18N
  SVC --> DOM
  SVC --> DB
  MIG --> SVC
  TOOLS2 --> MIG & INTG
```

**Layering rule**: `ui → services → db/domain`. Views never write SQL; services never
import Tk. Modules depend on services and the shared `AppContext` only, and hook into the
core through registration functions (`register_crop_handler`, `register_money_flow_handler`)
so the Counter behaves identically whether a module is installed or not. The assistant core
has no Tk, so a chat screen, a bot or a voice loop can use it. `services/updates.py` uses
the standard library only because it runs before anything else is imported. The reasons
for each choice are recorded in `v5/docs/adr/`.

## 2.7 Deployment view

```mermaid
flowchart LR
  subgraph PC ["Shop PC (Windows 10/11, Celeron, 4 GB)"]
    EXE["v5/ app folder<br/>Start High Table Holdings v5.bat → pythonw run.py<br/>(or a PyInstaller folder)"]
    DATA[("C:\\JBB\\v5\\hth.db (WAL)")]
    FOLDERS["backups/, logs/, exports/, bills/, pdfs/ ,<br/>updates/, assistant/, voice/"]
    OLD[("C:\\JBB\\v4, C:\\JBB\\data<br/>read only")]
    WORD["Microsoft Word (optional, DOCX→PDF)"]
    SAPI["Windows Hindi voice (SAPI)"]
    MIC["Microphone"]
  end
  GH[("GitHub: Parmodsihag/jbbv4<br/>branch v5, folder v5")]
  BROWSER[Browser - statements, WhatsApp web]
  EXE --> DATA
  EXE --> FOLDERS
  OLD -. "first start / import" .-> EXE
  EXE -.-> WORD
  EXE -.-> SAPI
  MIC -.-> EXE
  EXE --> BROWSER
  EXE -. "HTTPS: check, download" .-> GH
```
