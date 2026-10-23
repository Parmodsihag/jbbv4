# User guide

For the people at the counter: the shop owner (**admin**) and the shop staff (**employee**).
This guide covers High Table Holdings **5.7** in the **New** layout, which is the default.
The older sidebar layout (**Classic**) has the same features; see
[the v5 README](../README.md#screens) for its screens.

Every screenshot shows a made-up demo shop: names, phone numbers and amounts are invented.

**Contents:** [Signing in](#1-signing-in) · [The screen](#2-the-screen) ·
[Counter](#3-counter-every-entry) · [Khata](#4-khata-customers-and-their-accounts) ·
[Collections](#5-collections-promises-and-reminders) · [Today](#6-today-what-needs-doing) ·
[Stock](#7-stock) · [Money](#8-money) · [Reports](#9-reports) · [Ask](#10-ask-a-question) ·
[Hindi](#11-hindi) · [Settings](#12-settings) · [Shortcuts](#13-keyboard-shortcuts) ·
[Who can do what](#14-who-can-do-what) · [How the numbers work](#15-how-the-numbers-work) ·
[Questions](#16-common-questions)

---

## 1. Signing in

1. Start the program (on the shop PC: double-click **Start High Table Holdings v5**).
2. Type your username and password and press Enter.

* After five wrong passwords that username has to wait 30 seconds, then longer after each
  further mistake. Wrong attempts are written in the audit log.
* **Lock the screen** when you step away: `Ctrl+L`, or *Lock screen* in your user menu (your
  initial, top right). Whatever you were typing is still there after you unlock. The admin
  can make the screen lock by itself after some idle minutes (Settings › Appearance &
  language › Auto-lock).
* **Sign out** from the same menu. Someone else can then sign in.

The admin starts on **Today**; everyone else starts on the **Counter**.

## 2. The screen

<img src="../../docs/screenshots/counter.png" alt="The Counter screen" width="100%">

| part | what it does |
|---|---|
| Six areas across the top | **Today · Counter · Khata · Stock · Money · Reports**. Click one, or use its Alt key. |
| The Ask box | Find a customer or item by name, village, phone or number, *or* type a question for the Assistant. `Ctrl+K` puts the cursor there; the 🎤 button (or `F2`) asks by voice. |
| Date | Today's date. It changes by itself at midnight, and so do date boxes still showing yesterday. |
| ⚙ gear | Settings. |
| Your initial (top right) | Your user menu: who is signed in, *Lock screen*, light / dark, *Keyboard shortcuts*, *Switch to the classic layout* (admin) and *Sign out*. |
| Status line (bottom) | Messages, and when the last backup was taken. |

Tables everywhere work the same way: click a column title to sort, double-click or Enter to
open a row, `Ctrl+C` copies a row, right-click copies all rows (paste into Excel or
WhatsApp). Most lists have a find box that matches every word you type in any order
(`ram rohtak` finds *Ram Kumar, Rohtak*).

## 3. Counter: every entry

The Counter has four tabs, in shop words. You never have to think in debit and credit; the
small print under **Save** still says what will be booked.

| tab | use it when | books |
|---|---|---|
| **Sale** (`Alt+1`) | goods go out to a customer | debit (P) on their khata |
| **Purchase** (`Alt+2`) | goods or a crop come in from a supplier or farmer | credit (M) |
| **Payment in** (`Alt+3`) | the customer pays us | credit (M), into cash / bank / UPI |
| **Payment out** (`Alt+4`) | we pay someone | debit (P), out of cash / bank / UPI |

### Make a sale

1. **Pick the customer** in the box on the left (type part of the name, village, phone or
   number). Their balance, interest so far, open promise, last payment and last entries
   appear. Not there yet? **+ New customer** adds one without leaving the sale.
2. **Item**: start typing and pick it. The rate fills in from the last sale.
3. **Qty** and **Unit**. Loose sales are fine: 500 G of a KG item, 2.5 QTL of a crop kept in
   KG, 500 ML of a 1 LTR bottle. The rate is always per stock unit.
4. Press Enter on the rate (or **Add line**). Add as many lines as the customer takes.
   **Remove line** and **Clear all** fix mistakes.
5. **Interest**: leave *Charged · 24% a year* unless this sale should not earn interest.
6. **Paid now** (right side): if the customer pays part of it now, type the amount and
   choose CASH, a bank account or UPI. The rest goes on the khata. The right side shows
   *Items total*, *Paid now*, *Goes on khata* and the *Balance after*.
7. **Save sale** (`Ctrl+Enter`). Tick *Print slip after saving* for an 80 mm receipt.

All the lines and the payment are saved together. If anything is wrong, nothing is saved
and a message says what to fix.

### Take a payment

**Payment in** › pick the customer › amount › where it went (cash, bank, UPI) › Save.
If the customer had a promise, you can mark it **kept**. To close an account in full with a
discount, tick **Settle the account** (see [Settlement](#settlement)).

### Buy from a farmer, sell a crop

Pick a **crop** item (for example WHEAT) on **Purchase**: extra boxes appear for the gross
weight, the deduction (*kaat*) and the quality. Saving it records a **lot**: the farmer's
khata is credited and the stock goes up by the net weight.

On **Sale**, a crop is costed from the oldest lots first, and the cost and margin are shown
before you save. Selling more than is in stock is refused unless you tick *Allow selling
more than in stock*. A crop trade is saved on its own, not together with other lines.

### Undo a mistake

`Ctrl+Z` (or **Undo** at the bottom) removes the last entry you saved, if it was in the
last **15 minutes**: the khata rows, the stock movement, the cash-book line, the crop lot or
sale, and the item's last rate all go back. After 15 minutes ask the admin to correct the
khata.

**Today's entries** (bottom left) lists everything saved at the counter today.

## 4. Khata: customers and their accounts

<img src="../../docs/screenshots/khata.png" alt="A customer's khata page" width="100%">

**Khata › Customers** lists every account with its balance and the days since the last
entry. Filters: **All**, **Owe us**, **We owe**, **Quiet**, and a category (Cat) filter.
Red balances are owed to us, green are what we owe.

Click a customer to open their page:

* **Owes us / We owe**, split into the amount entered and the interest added so far.
* Buttons: **Sale**, **Payment in**, **Other entry** (Purchase, Payment out), **Promise**,
  **WhatsApp** (a balance message), **Statement**, and for the admin **More** (Edit
  customer, Category, Add ledger entry, Delete customer).
* Tabs: **Entries**, **Promises**, **Crop trades**, **Details**. The entries can show the
  *Current period* (since the last settlement), *This FY*, the *Last 90 days* or *All*.
  **Excel** exports what is shown.

**Statement** asks for a date range and opens a print-ready statement in the browser:
opening balance, every entry with its interest, totals, closing balance and the shop's name
and address. Print it, or *Save as PDF*.

**Admin corrections:** right-click an entry to edit or delete it. Deleting an entry says
what the new balance will be, and that the stock does not change. Entries that belong to a
crop lot or crop sale are changed from Stock › Crops & rates instead, so stock and costs
stay right.

## 5. Collections: promises and reminders

<img src="../../docs/screenshots/collections.png" alt="Collections" width="100%">

A *promise* (karar) is a date by which a customer said they will pay. **Khata ›
Collections** (`Alt+K`) sorts everyone who owes us into **Late**, **Today**, **Next 7
days**, **Later** and **Owe us, no promise**.

Pick a row: the right side shows a ready reminder (you can edit the text), **WhatsApp**
(opens a chat when the customer's details hold a 10-digit mobile number) and **Copy**.
Then record **what happened**: **Got payment**, **New date**, or **Kept**.
**Copy all reminders** copies one message per row shown.

To record a promise from a customer's page, use **Promise**. A new date on an open promise
moves it; the old dates stay in the promise history.

## 6. Today: what needs doing

<img src="../../docs/screenshots/today.png" alt="Today" width="100%">

The admin's home. The heading counts the things that need you:

* **Promises due**: late and due today, with **WhatsApp**, **Got payment** and **New date**
  on each row.
* **Stock running out**: items that will run out within a month at the current selling
  rate ("7.5 days"), and stock that is expiring. **Reorder list** opens the report.
* **Housekeeping**: default passwords still in use, debtors silent for 180+ days, no or old
  backup (**Back up now**), monthly expenses to post (**Post now**), data problems.
* **Today so far**: what we gave and got today, cash and other accounts.
* **Owed to us**: the total and how old it is (0–30, 31–90, 91–180, 180+ days).
* **Latest entries** at the counter, with who made them.

## 7. Stock

<img src="../../docs/screenshots/stock.png" alt="Stock" width="100%">

**Stock › Items** lists every item with what is in stock and the last rate. Filters:
**All**, **Running low**, **Out**, **Expiring**, **Not selling**. Pick an item to see its
type and GST rate, *In stock*, *Last rate*, *Sold in the last 30 days* and **Lasts about N
days**, with its **Movements** (newest first) and **Details**.

* **+ New item**: name, opening stock, unit, batch, expiry, GST rate and type (fertiliser,
  pesticide, seed, crop, other). Give seed, crop and liquid items KG or LTR so they can be
  sold loose.
* **Purchase · stock in** and **Sale** open the Counter for this item.
* **More** (admin): Edit item (this is where the unit is changed), Category, Add stock
  movement, Delete item. Double-click a movement to correct it.

**Changing an item's unit converts its whole history.** KG ↔ QTL ↔ G and LTR ↔ ML convert
by themselves. For unrelated units (PKT → KG) the program asks "how many KG is 1 PKT?"; leave
it blank to change only the label. Quantities and per-unit rates change; money amounts do not.

**Stock › Crops & rates** (`Alt+C`) shows crop lots and sales, the stock of each crop at
cost and at the latest market rate, market rates (typed in, or imported from a CSV file)
and the crop reports.

## 8. Money

<img src="../../docs/screenshots/money.png" alt="Money: the cash book" width="100%">

**Money › Cash book** (`Alt+F`):

* A tile per money account (cash box, bank, UPI) and the total. One is the *default for
  Counter*.
* A due-expenses bar: monthly expenses such as rent that are due, with **Post now**.
* The cash book for **Today**, **This week**, **This month** or the **Last 30 days**, with
  a running balance and who made each entry.
* **+ Expense** (to a head such as Rent or Electricity), **+ Other income**, **Transfer**
  between accounts, and **More** (*Capital in*, and *Drawings* when the owner takes money
  out).
* *This month so far*: money in, money out and expenses by head; **P&L** opens profit and
  loss.

Customer payments taken at the Counter appear here by themselves; you do not enter them
twice.

**Money › GST bills** (`Alt+B`): make a GST invoice (pick a customer or type a name, add
lines, see the tax, *Save & create DOCX*; *PDF* when Microsoft Word is on the PC), browse
bills by month, open, make a PDF, or merge a range of bills into one PDF. The admin also
has the month-end batch.

**Money › Reports & setup** (admin): cash flow, profit and loss, expenses by head, monthly
expenses, account balances; money accounts, expense heads and recurring expenses.

## 9. Reports

<img src="../../docs/screenshots/reports.png" alt="Reports catalogue" width="100%">

**Reports** (`Alt+R`) is one catalogue of 34 reports: aging, interest, day book, collections
list, reorder suggestions, GST summary, crop margins, cash flow and more. Type in the find
box ("aging", "gst", "lots", "profit") to narrow the list. Click ☆ to **pin** a report you
use often; pinned reports stay at the top.

Every report sorts by any column, has a **Filter rows** box, and exports to **Excel**.
Double-click a row to open that customer's khata or that item.

Customer and item reports have a **Scope**: *Per settings* leaves out the categories the
admin excluded (normally E, the defaulters); *All categories* shows everyone.

Some reports are for the admin only: audit log, data check, staff activity, and the money
reports (cash flow, profit and loss, expenses).

## 10. Ask a question

<img src="../../docs/screenshots/assistant.png" alt="The Assistant answering in Hindi" width="100%">

Type a question in the Ask box the way you would ask a person, in Hindi, Hinglish or
English, and press Enter. The answer comes back in the language you used, with a table and
a button to the full screen or report.

| ask | get |
|---|---|
| *Ramesh ka last month ka hisab btao* | "Which Ramesh?" with each one's village and phone, then his ledger for last month |
| *यूरिया कितना बचा है* · *dap ka bhav* | stock left, or the selling rate |
| *kiske karar ki tarikh nikal gayi* | late promises with balances |
| *pichle mahine kitni bikri hui*, then *aur is mahine?* | sales for each month |
| *sabse bade 10 bakayedar* · *collection list* · *kya mangwana hai* | the lists |

* If it is not sure, it **asks back**. Answer with the number, *rohtak wala*, *dusra*, or the
  last digits of the phone. *chhodo* cancels.
* A follow-up within two minutes (*aur …*, *uska phone*) reuses the last question.
* It **only looks things up**. It never changes anything, and it shows each person only what
  their role allows (an employee is not shown profit).

**By voice:** press 🎤 or `F2` and speak. The words appear as they are heard; the question
goes by itself 1.2 seconds after you stop (tap the text to correct it first). Answers to
spoken questions are spoken back in Hindi. A USB or headset microphone works much better
than a laptop's built-in one.

## 11. Hindi

**Settings › Appearance & language › Language: English / हिन्दी** switches every screen,
report, statement, slip and Excel export to Hindi at once, for the whole shop.

<img src="../../docs/screenshots/counter-hindi.png" alt="Counter in Hindi" width="100%">

* Every customer and item has a Hindi copy of its name, made by the program. Correct one in
  *Edit customer* / *Edit item*, or in **Settings › Hindi names › Review / correct names**.
  A corrected name is marked ✓ and never changed by the program again.
* The books themselves stay in English, so switching back loses nothing. Search boxes find
  names typed in English while the screens are in Hindi.
* Reminders and WhatsApp balance messages have their own Hindi wording (Settings ›
  Reminder messages, while in Hindi).
* Chart labels stay in English letters.

## 12. Settings

The gear (`Alt+T`) opens Settings in sections. Sections marked ADMIN are for the admin.

| section | what is there |
|---|---|
| Shop details (admin) | name, address, phone, GSTIN, licences, footer: printed on statements and slips |
| Appearance & language | language; layout (admin: New / Classic for the whole shop); **Mode** light / dark / system; **Colours** (seven themes, each light and dark, including *High contrast*); numbers Indian 12,34,567.00 or international 1,234,567.00; text size 90–130 %; auto-lock |
| My password | change your own password |
| Users (admin) | add users, reset a password, change a role, deactivate |
| Backup & data (admin) | back up now, automatic daily backup and how many to keep, restore a backup, import v3 data, *Run setup wizard* again |
| Reminder messages | the reminder wording, in English and in Hindi |
| Categories (admin) | which categories reports include, re-score customers, auto-categorise items |
| Hindi names | review and correct Hindi copies; fill missing; regenerate the automatic ones |
| Assistant & voice | speak answers (when I speak / always / never), microphone and *Test microphone*, install a voice model or the optional language model |
| Updates (admin) | check for updates, install, restart, undo the last update |
| About | version |

## 13. Keyboard shortcuts

`F1` shows all of these on screen.

| keys | where |
|---|---|
| `Alt+D` | Today |
| `Alt+S` | Counter |
| `Alt+A` · `Alt+K` | Khata › Customers · Khata › Collections |
| `Alt+I` · `Alt+C` | Stock › Items · Stock › Crops & rates |
| `Alt+F` · `Alt+B` | Money › Cash book · Money › GST bills |
| `Alt+R` | Reports |
| `Alt+T` · `Alt+U` | Settings · Users (admin) |
| `Alt+H` | Ask (the Assistant) |
| `Ctrl+K` | the Ask / search box |
| `F2` | ask by voice |
| `Ctrl+L` | lock the screen |
| `F1` | this list |

On the Counter:

| keys | does |
|---|---|
| `Alt+1` … `Alt+4` | Sale · Purchase · Payment in · Payment out |
| `Enter` | quantity → rate → add the line |
| `Ctrl+Enter` | save the open tab |
| `Ctrl+Shift+Enter` | save a Purchase or a Payment in (never a sale) |
| `Ctrl+Z` | undo the last entry (15 minutes) |
| `Alt+Up` / `Alt+Down` | next / previous day in a date box |

## 14. Who can do what

| | admin | employee |
|---|:---:|:---:|
| Counter: sales, purchases, payments; undo your own last entry | ✓ | ✓ |
| Add customers and items | ✓ | ✓ |
| Promises and reminders | ✓ | ✓ |
| Reports and Excel (except the admin reports) | ✓ | ✓ |
| Cash book entries, GST bills, crop trades | ✓ | ✓ |
| Correct or delete entries, items, customers | ✓ | – |
| Audit log, data check, staff activity, finance reports | ✓ | – |
| Users, backups, restore, v3 import, updates | ✓ | – |
| Shop-wide settings (shop details, layout, number style, categories, auto-lock) | ✓ | – |
| GST month-end batch | ✓ | – |

Every change records who made it, in the audit log.

## 15. How the numbers work

These rules are the shop's own and have not changed since the first program.

* **Interest** is 24 % a year, counted per day (`0.24 / 365`). On **31 March** each year the
  interest so far is added to the amount, and next year's interest is counted on the total.
* **Tags.** Each entry is *1 Normal* (earns interest), *2 No interest*, or *0 Settle*.
* **Balance** = what the customer took (with interest) minus what they paid (with interest),
  counted from the last settlement.

### Settlement

Settling closes an account in full, for example when a customer pays a round figure and you
let the rest go. The program writes three rows: the payment, the *Settled Amount* (the
balance before), and the *Discount* (the difference, which can be negative if they paid
more). The balance becomes zero and a new period starts from the next entry.

## 16. Common questions

**The balance changed although nobody entered anything.** Interest is added every day on
tag-1 entries. *Owes us* shows the amount entered and the interest separately.

**I saved a sale to the wrong customer.** Within 15 minutes: `Ctrl+Z` on the Counter. Later:
ask the admin to delete it from that customer's khata (right-click the entry).

**WhatsApp does not open.** The customer's details need a 10-digit mobile number. Add it in
*Edit customer*.

**The Assistant says it heard nothing.** Check *Settings › Assistant & voice › Microphone*
and press *Test microphone*. Choose the real microphone, never "Stereo Mix".

**The screen went dark and asks for a password.** The screen locked itself. Type your
password; your work is still there. *Sign in as someone else* signs you out.

**Something says "Something went wrong".** Note what you clicked and tell the admin; the
details are written to the log file (see the [admin guide](ADMIN_GUIDE.md#7-troubleshooting)).
