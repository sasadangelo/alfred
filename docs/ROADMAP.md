# Alfred roadmap

This page collects where Alfred is going: what is already there, what comes next, and the ideas still to explore. It is a plan, not a promise: priorities change as features are tried in daily use.

Alfred is a Claude Code plugin. Skills hold the behavior, MCP servers expose neutral tools, and personal data stays on the user's computer.

## Available

| Area | What Alfred does |
|---|---|
| Google Calendar | List, search, create, update and delete events; recurring series; reminders; availability |
| Google Tasks | Lists, tasks, subtasks and due dates |
| Gmail | Search, read, label, archive, mark read or unread, trash and restore (no sending, no permanent deletion); save attachments into folders |
| Weather | Forecasts and alerts, with running and commute advice |
| Traffic | Car routes with live and predicted traffic, departure times for appointments and the commute |
| Fuel prices | Cheapest stations near a place for the user's fuel, saved stations, with the time each price was communicated |
| User profile | Family, places with coordinates, vehicles with yearly deadlines, habits and preferences |
| Utilities and subscriptions | Providers, codes (POD, PDR, contract), billing frequency, renewals, the Gmail query for their emails and where their bills go, in `subscriptions.yaml` |

## Next

Ordered by usefulness against effort.

1. **Places nearby.** Supermarkets, fuel stations and other services around home or work.
2. **Energy offer check.** See [Energy offers](#energy-offers) below.
3. **News.** A news service on its own, from RSS feeds the user chooses (general, sports, technology, science): latest headlines by source or topic, short summaries in Italian, similar stories from different sources grouped together, and a "read later" list. Free and keyless; the feeds are configured by the user.
4. **Daily almanac.** See [Almanac](#almanac) below.
5. **Morning routine.** A daily briefing built from the existing skills (weather, appointments, tasks, birthdays, deadlines, commute), the news service and the almanac. To decide: how it is delivered (chat, a Telegram bot, or an email to oneself) and when it runs.
6. **Projects.** A project is a container with its own goal and rules, a task list, recurring calendar reminders, a document folder, a mail label and a log of decisions. Alfred loads a project's rules when the user talks about it. First candidate: a recurring household administration task with fixed rules and a two-month cycle.
7. **Shopping module.** See [Shopping](#shopping) below.
8. **Document archive and backup.** See [Documents](#documents) below.

## Ideas

### Home and family

- **Household deadlines:** identity documents, appliance maintenance, product warranties, with reminders well ahead of time (the same mechanism as vehicle deadlines).
- **Weekly review:** on Sunday evening, the week's appointments, open tasks, running weather and upcoming deadlines.
- **Gift ideas** a few days before a birthday, based on what the profile says about the person.
- **Trips:** itinerary, check-in and destination weather in the calendar, from booking emails.
- **School:** a digest of school communications that arrive by email.

### Running and health

- **Running playlists** matched to the workout (easy run, intervals, long run).
- **Training log** from Strava, with weekly trends and race reminders.
- **Health:** periodic checkups and archived medical reports.

### Interests

- **Book and music discovery,** with a "to read" or "to listen" list.
- **Art practice:** a study plan for ongoing courses and practice reminders.
- **Chess:** daily puzzle and game review from lichess.
- **Stargazing:** whether tonight's sky is worth it, from cloud cover and astronomical data.
- **Genealogy:** family tree research.

### Energy offers

Linked to `subscriptions.yaml`: each electricity (and later gas) entry gains the current offer, its price per kWh, fixed fee, the end of the fixed-price period and the early exit fee.

1. **Consumption from the bills.** Monthly kWh by time band (F1, F2, F3), the yearly total and the cost per bill are read from the saved PDFs, so the comparison uses real consumption, not estimates.
2. **Official offers.** ARERA's Portale Offerte publishes every offer daily as open data (free, keyless). Alfred keeps only the fixed and variable offers valid for the supply's area, power and customer type, and estimates the yearly cost of the supply part (energy with network losses, fixed fee, dispatching), the only part that changes between suppliers.
3. **Comparison.** The current contract against the best offers, with the saving net of the early exit fee for the months left. Offers reserved to other customers (for example "only for customers coming from another supplier") or areas are excluded.
4. **When it runs.** Checking is not switching. A quiet check every six months, plus one four months before the fixed-price period ends and one when the supplier announces new conditions. The user is told only when the net saving exceeds a threshold they choose (for example 100 € a year); during a fixed-price period a switch is suggested only for a large saving (for example 200 € a year, net of the exit fee), so changes stay rare: usually one per fixed-price period.
5. **Limits.** Estimates, not advice: the user checks the conditions on the supplier's site and on ilportaleofferte.it before signing. Alfred never signs or switches on the user's behalf.

### Almanac

A daily dose of curiosity, each item with a link to go deeper; on request Alfred reads the linked page and tells more.

| Section | Content | Source |
|---|---|---|
| On this day | 3 items (events, births or deaths) from different eras, preferring the interests in the user's profile | The Italian Wikipedia page of the day (sections Eventi, Nati, Morti), free and keyless; Wikimedia's "On this day" feed if it covers Italian |
| Saint of the day | The saint or saints celebrated, with a line on who they were | The *Feste e ricorrenze* section of the same page |
| Word of the day | An uncommon but real Italian word, its meaning, its origin and a curious example sentence | Candidates and meanings from Wikizionario (open license); Claude writes the example sentence |
| Horoscope | The day's horoscope for the user's sign, and on request for family members, from birth dates in the profile; quoted from the source with its link, never written by Claude | TPI's horoscope RSS feed (tpi.it/oroscopo/feed), updated daily with Paolo Fox and Branko; the user picks the astrologer |

**Memory.** A local file in the data directory records what was shown and when, so an item is not shown again the following year, and a word is never repeated. The user can mark an item as interesting, to find it again later.

**Delivery.** On request ("cosa è successo oggi?", "parola del giorno", "oroscopo") and as a section of the morning routine.

### Shopping

A dedicated module, because shopping has its own data and rules: a library with a local SQLite database in Alfred's data directory, command-line scripts, an MCP server and a skill. Calculations (what is running out, unit prices, store comparison) are done in code; Claude reads receipts and labels and leads the conversation.

**Data**

| Item | Main fields |
|---|---|
| Stores | Name, chain, address and coordinates, notes |
| Categories | Name and order, for example the aisle order of the usual store |
| Products | Name, category, brand, size (g, ml, pieces), preferred store, recurring or not, frequency set by the user (optional), barcode (optional) |
| Purchases | Product, store, date, optional quantity and price |
| Flyer offers | Store, product, price, validity period; entered by the user, by text or from a photo |
| Lists | The current list and what has been ticked |

**Making the list**

1. Products that are probably running out come first: time since the last purchase compared with the product's usual frequency, set by the user or learned from past purchases.
2. The rest of the catalog follows, by category, to scroll quickly.
3. Valid offers on listed products are pointed out.
4. The list goes to Google Tasks, split by store if needed, to tick on the phone.
5. Ticked items are recorded as purchases, so the next proposal is more accurate.

**Phases**

1. Stores, categories, catalog and shopping list, with the Google Tasks round trip.
2. Flyer offers entered by hand, also from a photo.
3. Prices: receipts, shelf labels (which show the price per kg or litre) and barcodes via Open Food Facts for package sizes, so every price becomes a unit price.
4. Store comparison for a whole list, and advice for large stock-up shopping.

Receipts show the package price but not the size: the size is stored once per product in the catalog, so later receipts are enough to compute the unit price. From the phone, Google Tasks covers ticking; a Telegram bot, shared with the morning routine, could receive photos of receipts and labels.

### Documents

The documents of the paperless home (bills, contracts, medical reports, scans) live in one local folder, `~/Documents/Alfred`, organized by area (`Bollette/Casa/Luce`, `Salute`, ...) with file names that sort by period (for example `Illumia_Ottobre-Novembre_2025.pdf`). The local folder is the source of truth. Syncing is not backup: a file deleted or damaged locally is deleted or damaged in a synced copy too. Backups follow the 3-2-1 rule: three copies, on two kinds of media, one of them away from home.

| Level | Purpose | Examples |
|---|---|---|
| Local archive | The originals, where Alfred files and renames documents | `~/Documents/Alfred` |
| Short-term backup | Hourly versions to restore a deleted or overwritten file in a click | Time Machine on an external disk (already in macOS, no cost) |
| Long-term backup, off site | Survives the loss of both computer and disk (theft, fire); kept cheaply for years | restic snapshots, encrypted on the computer, to S3-compatible "hot" storage with immediate access: Backblaze B2, AWS S3 Standard, Wasabi |
| Phone access (optional) | Read documents from the phone or share them with the family | Google Drive (`drive.file` permission, only the files Alfred creates), Dropbox; only if really needed, without the most sensitive documents or with them encrypted |

**Why restic instead of zip files.** Snapshots are encrypted before they leave the computer, so the provider only stores unreadable data (bills carry tax codes, POD, PDR and bank details). Only changes are uploaded, deduplicated. `restic check` verifies the archive, while a single corrupted zip loses everything inside it. If zip files are preferred: one archive per year, encrypted (for example with `age`), in a cold storage class with Object Lock. At a few GB in total the cost is a few cents a month.

**Why not Glacier for restic.** Cold classes are slow to read back: S3 Glacier Flexible Retrieval takes minutes to 12 hours, Deep Archive 12 to 48 hours (Glacier Instant Retrieval is immediate but charges every GB read and bills each file for at least 90 days). restic needs to read its own index to back up, check and restore, which cold classes do not allow without a restore request first. For a few GB, hot storage costs cents anyway; cold storage pays off only at terabyte scale (for example a photo archive). Delay is acceptable for the off-site copy, which is needed only after a disaster: everyday restores come from the local archive or Time Machine.

**What Alfred does.** Alfred does not implement storage; it orchestrates existing tools.

1. Documents arrive mostly as email attachments (bills, invoices, fines, receipts) or are added by the user; Alfred files and renames them in the local archive, removes exact duplicates (same document number and text) and, when they have a due date, creates a task or reminder.
2. Runs the restic backup on a schedule and records the outcome.
3. Warns when the last successful backup (Time Machine or restic) is too old, for example in the morning routine: a backup failing silently is the most common risk.
4. Once a year proposes a restore test: a random file is restored and compared with the original.
5. Optionally, a retention policy per document type, set by the user, says how many years a document stays in the local archive before it lives only in the backup.

**Safeguards**

- Files are encrypted on the user's computer before they reach the off-site backup; the keys and the restic password never leave it, and their loss means the loss of the backup, so the user keeps a copy in a safe place (for example a password manager).
- A local index records every document (type, date, origin, where it is now), so Alfred can always find and restore it.
- Nothing is deleted from the local archive until the backup copy is verified, and every move is logged; duplicates go to the system trash, never deleted for good.
- Retention years are decided by the user per type; legal retention periods vary by document, and for tax documents an accountant should be consulted.

### Mail

- **Unsubscribe** from newsletters with one-click unsubscribe.
- **Filters** that label, archive or trash future mail from a sender automatically.

### Photos

- **Print albums:** help prepare albums to print from a folder of original photos (resolution, duplicates, order).

### Maintenance

- **Clear messages for network timeouts** to Google, as already done for HTTP errors.
- **Domains and websites:** renewal deadlines and availability checks.

## Constraints to keep in mind

| Topic | Constraint |
|---|---|
| TomTom free plan | The geocode endpoints are not included; Alfred uses general search with an OpenStreetMap fallback. |
| Google Photos | Since 2025 the API lets an app manage only the photos and albums it created, or those the user picks each time. Alfred cannot reorganize existing albums. |
| Spotify | Playlists can be created through the API, but tempo data and automatic recommendations are no longer available to new apps since late 2024 (to verify). |
| Supermarket flyers | Flyer aggregators have no public API and do not allow automated reading; offers are entered by the user. |
| Supermarket prices | No public price API in Italy; prices come from the user's receipts, shelf labels and online orders. |
| School register | Classeviva has no official API. |
| Gmail sending | Not granted today; needed only for features that send mail. |

## Decisions taken

- Alfred is the agent; MCP servers are neutral tools, and behavior lives in skills.
- One Google authorization covers Calendar, Tasks and Gmail; deletion means trash, never permanent.
- Personal data stays in the plugin data directory on the user's computer and never in the repository.
- Personal finances are out of scope: they are handled by a separate system.
- The old WhatsApp morning report was removed; the new morning routine will be built from the skills.
