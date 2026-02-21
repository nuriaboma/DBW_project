# 💊 RXInsight

A Flask-based web application for checking drug interactions and side effects, finding medications by condition, and managing patient medication profiles.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Local Setup](#local-setup)
- [Project Structure](#project-structure)
- [Features & Updates](#features--updates)
- [Troubleshooting](#troubleshooting)

---

## Overview

RXInsight provides:

- Drug interaction checker with severity warnings (authenticated users)
- Public interaction check — no login required
- Find medications by disease or condition
- User profile with search history
- Platform statistics dashboard
- PDF export of drug analysis reports
- Autocomplete on all drug and condition search fields

---

## Prerequisites

Make sure you have the following installed:

- **Python 3.9+** — check with `python3 --version`
- **pip** — included with Python

---

## Local Setup

### 1. Get the project files

Place all project files in a folder, for example `~/Desktop/RXInsight/`.

### 2. Open a terminal in the project folder

On Mac, right-click the folder → **New Terminal at Folder**.

### 3. Create a virtual environment

```bash
python3 -m venv .venv
```

### 4. Activate the virtual environment

**Mac / Linux:**
```bash
source .venv/bin/activate
```

**Windows:**
```bash
.venv\Scripts\activate
```

> You'll see `(.venv)` at the start of your terminal prompt when it's active. **You need to do this every time you open a new terminal.**

### 5. Install dependencies

```bash
pip install -r requirements.txt
```

### 6. Run the application

```bash
python run.py
```

Then open your browser and go to: **http://127.0.0.1:5000**

> 💡 To stop the server, press `Ctrl + C`.

---

## Project Structure

```
RXInsight/
├── app/
│   ├── __init__.py
│   ├── models.py
│   ├── routes.py
│   ├── forms.py
│   └── templates/
│       ├── base.html
│       ├── home.html
│       ├── index.html
│       ├── login.html
│       ├── register.html
│       ├── user.html
│       ├── stats.html                ← new
│       ├── public_interactions.html
│       └── public_conditions.html
├── run.py
├── setup_db.py
├── import_data.py
├── fix_table.py
├── update_db.py
└── requirements.txt
```

---

## Features & Updates

The following features were added on top of the base application.

---

### 1. 📊 Platform Statistics Dashboard

A `/stats` page for logged-in users showing live data from the database.

**Files changed:**
- `stats.html` — new template, add to `app/templates/`
- `stats_route.py` — paste the route into `app/routes.py`
- `base.html` — updated nav bar with a "Stats" link for authenticated users

**What it shows:**
- Animated KPI cards: total searches, interactions found, registered users, drugs in DB, known interactions
- Line chart: searches over the last 7 days
- Bar chart: top 5 most searched drugs
- Most active users table with activity bars
- Database breakdown: avg side effects per drug, drug with most side effects, most searched drug

---

### 2. 📄 PDF Export of Drug Analysis

After running a drug search, logged-in users can download a formatted PDF report.

**Files changed:**
- `new_routes.py` — paste the `/export-pdf` route into `app/routes.py`
- `index.html` — updated with an "Export PDF" button next to the results heading

**Install the required dependency:**
```bash
pip install reportlab
```
Add `reportlab` to your `requirements.txt`.

**The PDF includes:**
- Patient profile table (age, gender, condition, medications)
- Critical interactions highlighted in red with severity badges
- Drug-by-drug side effects in a two-column layout
- Disclaimer footer
- Auto-timestamped filename (e.g. `RXInsight_Report_20260219_1430.pdf`)

---

### 3. 🔍 Drug & Condition Autocomplete

Type-ahead suggestions on all search inputs. Uses a lightweight `fetch()` call — no extra libraries needed.

**Files changed:**
- `new_routes.py` — paste the `/api/drugs` and `/api/conditions` routes into `app/routes.py`
- `index.html` — autocomplete on the medications input
- `public_interactions.html` — autocomplete on the interaction checker input
- `public_conditions.html` — autocomplete on the condition search input

**Behaviour:**
- Suggestions appear after typing 2+ characters
- Keyboard navigation: `↑` `↓` to move, `Enter` to select, `Escape` to close
- Drug inputs: selecting a suggestion appends to the comma-separated list (supports multiple drugs)
- Condition input: selecting a suggestion fills the whole field

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'flask'`**  
You forgot to activate the virtual environment. Run Step 4 again before any Python command.

---

**No medications / interactions found in search**  
Your database may have empty or `N/A` condition fields. Inspect with:

```bash
python3 -c "
from app import app, db
from app.models import Drug
with app.app_context():
    for d in Drug.query.limit(10).all():
        print(d.name, '|', d.condition)
"
```

To manually fix a drug's condition:
```bash
python3 -c "
from app import app, db
from app.models import Drug
with app.app_context():
    Drug.query.filter_by(name='Aspirin').first().condition = 'Headache, Pain, Fever'
    db.session.commit()
"
```

---

**`AttributeError` in stats or export routes**  
The model field names in `new_routes.py` may not match your actual models. Check that `User.iduser`, `SearchHistory.medications`, and `SearchHistory.user_id` match what's defined in `app/models.py`.

---

**PDF export returns an error**  
Make sure reportlab is installed: `pip install reportlab` and that it's listed in `requirements.txt`.

---

*© 2026 RXInsight Team*
