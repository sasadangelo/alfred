# Alfred roadmap

This page collects where Alfred is going: what is already there, what comes next, and the ideas still to explore. It is a plan, not a promise: priorities change as features are tried in daily use.

Alfred is a Claude Code plugin. Skills hold the behavior, MCP servers expose neutral tools, and personal data stays on the user's computer.

## Available

| Area | What Alfred does |
|---|---|
| Google Calendar | List, search, create, update and delete events; recurring series; reminders; availability |
| Google Tasks | Lists, tasks, subtasks and due dates |
| Gmail | Search, read, label, archive, mark read or unread, trash and restore (no sending, no permanent deletion) |
| Weather | Forecasts and alerts, with running and commute advice |
| Traffic | Car routes with live and predicted traffic, departure times for appointments and the commute |
| Fuel prices | Cheapest stations near a place for the user's fuel, saved stations, with the time each price was communicated |
| User profile | Family, places with coordinates, vehicles with yearly deadlines, habits and preferences |

## Next

Ordered by usefulness against effort.

1. **Places nearby.** Supermarkets, fuel stations and other services around home or work.
2. **News.** A news service on its own, from RSS feeds the user chooses (general, sports, technology, science): latest headlines by source or topic, short summaries in Italian, similar stories from different sources grouped together, and a "read later" list. Free and keyless; the feeds are configured by the user.
3. **Morning routine.** A daily briefing built from the existing skills (weather, appointments, tasks, birthdays, deadlines, commute) and the news service. To decide: how it is delivered (chat, a Telegram bot, or an email to oneself) and when it runs.
4. **Projects.** A project is a container with its own goal and rules, a task list, recurring calendar reminders, a document folder, a mail label and a log of decisions. Alfred loads a project's rules when the user talks about it. First candidate: a recurring household administration task with fixed rules and a two-month cycle.
5. **Shopping module.** See [Shopping](#shopping) below.
6. **Document archive.** See [Documents](#documents) below.

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

Two levels, each with interchangeable providers:

| Level | Purpose | Examples |
|---|---|---|
| Working archive | Recent documents, organized by type and year, reachable from the phone | Google Drive (`drive.file` permission, only the files Alfred creates), Dropbox |
| Backup archive | Old documents, kept cheaply for years; slower to retrieve | S3-compatible storage: AWS S3 (Glacier classes), Backblaze B2, Wasabi |

**Flow**

1. Documents arrive mostly as email attachments (bills, invoices, fines, receipts) or are added by the user; Alfred files them in the working archive and, when they have a due date, creates a task or reminder.
2. A retention policy per document type, set by the user, says how many years a document stays in the working archive.
3. When that time is up, the document is copied to the backup archive, the copy is verified, and only then it is removed from the working archive.
4. Optionally, after a further number of years, it is deleted from the backup too.

**Safeguards**

- Files are encrypted on the user's computer before they reach the backup archive; the keys never leave it.
- A local index records every document (type, date, origin, where it is now), so Alfred can always find and restore it.
- Nothing is deleted from the working archive until the backup copy is verified, and every move is logged.
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
