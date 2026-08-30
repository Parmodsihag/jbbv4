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
  P0((0<br/>High Table<br/>Holdings v4))
  FILES[Excel · HTML statement · DOCX/PDF invoice · Backup]

  ADM -- "credentials, entries, corrections,<br/>user & settings changes, import request" --> P0
  EMP -- "credentials, sales / receipts,<br/>new accounts & items, krar" --> P0
  P0 -- "dashboard, ledgers, reports,<br/>alerts, audit log" --> ADM
  P0 -- "balances, today's entries,<br/>reminder text" --> EMP
  P0 -- "statement, invoice, WhatsApp reminder" --> CUST
  V3 -- "customers, ledgers, items, krar, notes" --> P0
  P0 -- "exports, backups" --> FILES
```

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
  P8((8<br/>Feature modules<br/>bills · crops · finance))

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

## 2.5 Entity-relationship diagram

```mermaid
erDiagram
  users {
    int id PK
    text username UK
    text full_name
    text role "admin | employee"
    text password_hash
    text salt
    int is_active
  }
  customers {
    int id PK
    text name
    text other_details
    text category "A-E"
    int category_locked
  }
  transactions {
    int id PK
    int customer_id FK
    text date
    text description
    real amount
    text type "P | M"
    text tag "0 | 1 | 2"
    int legacy_id
    text created_by
  }
  items {
    int id PK
    text name
    real stock_value
    real last_value
    text unit
    text batch
    text expiry_date
    real gst_rate
    text item_type "F P S C O"
    text pakka_kacha
    text category
  }
  item_transactions {
    int id PK
    int item_id FK
    text date
    real received
    real sale
    real value
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
    text code "01-12"
    text detail
    text username
    text at
  }
  settings {
    text key PK
    text value
  }
  bills {
    int id PK
    int number
    text date
    int customer_id FK
    text customer_name
    real taxable
    real cgst
    real sgst
    real total
  }
  bill_lines {
    int id PK
    int bill_id FK
    int item_id FK
    real qty
    real rate
    real tax_rate
  }
  crop_lots {
    int id PK
    int item_id FK
    int customer_id FK
    text date
    real gross
    real deduction
    real net
    real rate
    text quality
    real remaining
  }
  crop_sales {
    int id PK
    int item_id FK
    int customer_id FK
    real qty
    real rate
    real cost
    real margin
    int short_flag
  }
  crop_sale_lots {
    int sale_id FK
    int lot_id FK
    real qty
    real cost
  }
  crop_rates {
    int item_id FK
    text date
    real rate
  }
  money_accounts {
    int id PK
    text name
    real opening
    int is_default
  }
  expense_heads {
    int id PK
    text name
    text kind "expense | income"
  }
  finance_entries {
    int id PK
    int account_id FK
    int head_id FK
    text kind
    text date
    real amount
    int transaction_id FK
  }
  finance_recurring {
    int id PK
    int head_id FK
    int account_id FK
    real amount
    int day_of_month
  }

  customers ||--o{ transactions : "has"
  customers ||--o{ krar : "promises"
  krar ||--|{ krar_dates : "dates"
  items ||--o{ item_transactions : "moves"
  customers ||--o{ bills : "billed"
  bills ||--|{ bill_lines : "lines"
  items ||--o{ bill_lines : "priced"
  items ||--o{ crop_lots : "crop"
  customers ||--o{ crop_lots : "farmer"
  items ||--o{ crop_sales : "crop"
  customers ||--o{ crop_sales : "buyer"
  crop_sales ||--|{ crop_sale_lots : "FIFO"
  crop_lots ||--o{ crop_sale_lots : "allocated"
  items ||--o{ crop_rates : "market"
  money_accounts ||--o{ finance_entries : "book"
  expense_heads ||--o{ finance_entries : "head"
  transactions ||--o| finance_entries : "linked"
  expense_heads ||--o{ finance_recurring : "template"
  money_accounts ||--o{ finance_recurring : "from"
```

Key integrity rules: all foreign keys `ON DELETE CASCADE`; `CHECK` constraints on
`type`, `tag`, `role`; indexes `ix_tx_customer_date (customer_id, date, id)`,
`ix_itx_item_date (item_id, date, id)`, `ix_krar_customer (customer_id, is_nill)`;
schema version in `PRAGMA user_version` with migrations 1 (core) → 2 (bills) → 3 (crops)
→ 4 (categories) → 5 (finance).

## 2.6 Architecture

```mermaid
flowchart TB
  subgraph UI ["hth/ui — presentation (customtkinter)"]
    APP[app.py shell: sidebar, shortcuts, toasts]
    VIEWS[views: dashboard · sales · customers · items · karar · reports · settings · users · login · setup]
    WID[widgets: datatable · searchbox · forms · dialogs · kpi · charts · palette]
    CTX[AppContext: db, services, user, navigate, toast]
  end
  subgraph MODS ["hth/modules — optional features"]
    BILLS[bills]
    CROPS[crop_trading]
    FIN[finance]
  end
  subgraph SVC ["hth/services — business logic (no Tk)"]
    ACC[accounts] --- SAL[sales] --- INV[inventory]
    KR[krar] --- REP[reports] --- AUD[audit]
    AUTH[auth] --- PERM[permissions] --- EXP[export]
    INTG[integrity] --- BKP[backup] --- CAT[categories]
    STM[statements] --- REM[reminders] --- SRCH[search] --- SET[settings]
  end
  subgraph DOM ["hth/domain — pure rules (no I/O)"]
    INT[interest.py]
    UNITS[units.py]
    CONST[constants.py]
    MODELS[models.py dataclasses]
  end
  subgraph DB ["hth/db"]
    CONN[connection.py: transaction-scoped, re-entrant]
    SCHEMA[schema.py: versioned migrations]
  end
  MIG[hth/migration/from_v3.py]
  TOOLS[tools: migrate_v3.py · check_data.py]

  APP --> VIEWS --> WID
  VIEWS --> CTX --> SVC
  VIEWS --> MODS --> SVC
  MODS -. register handlers .-> SAL
  SVC --> DOM
  SVC --> DB
  MIG --> SVC
  TOOLS --> MIG & INTG
```

**Layering rule**: `ui → services → db/domain`. Views never write SQL; services never
import Tk. Modules depend on services and the shared `AppContext` only, and hook into the
core through registration functions (`register_crop_handler`, `register_money_flow_handler`)
so the Sales screen behaves identically whether a module is installed or not.

## 2.7 Deployment view

```mermaid
flowchart LR
  subgraph PC ["Shop PC (Windows 10/11)"]
    EXE["HighTableHoldings/ (PyInstaller folder)<br/>or python run.py"]
    DATA[("C:\\JBB\\v4\\hth.db")]
    EXPORTS["exports/ · bills/ · pdfs/ · backups/ · logs/"]
    WORD["Microsoft Word (optional, DOCX→PDF)"]
  end
  BROWSER[Browser — statements, WhatsApp web]
  EXE --> DATA
  EXE --> EXPORTS
  EXE -.-> WORD
  EXE --> BROWSER
```
