# Logos Notes → Readwise Exporter

A small, free tool that copies your **Logos Bible Software** notes and highlights
into a spreadsheet file (a "CSV") that you can import into **[Readwise](https://readwise.io)**.

It was written for pastors, teachers, and Bible students who have built up years
of notes in Logos and want them flowing through Readwise's daily review — without
hand-copying a single one.

You do **not** need to be a programmer to use this. The steps below walk through
everything, including how to open the Terminal for the first time.

**Please read this file carefully before attempting to import into Readwise**

If you make a mistake, you can delete in Readwise and try again.

---

## What it does

For every note and highlight in a Logos notebook, it creates one row containing:

- **The note you wrote**, formatted nicely (bold, bullet points, and links preserved).
- **A clickable link back to the exact spot in Logos** (so one click reopens the
  passage in your Logos app).
- **Your Logos tags**, placed so Readwise can recognize them.
- **The date** you created the note.
- **Optionally, the highlighted passage itself** — the actual sentence you
  highlighted in the book (see [Recovering highlighted text](#optional-recovering-the-highlighted-text)).

Everything runs **on your own computer**. Nothing is uploaded anywhere, and your
Logos files are only ever *read*, never changed.

---

## Before you begin

You'll need:

1. **A computer with Logos installed** (Mac or Windows) where your notes have synced.
2. **Python 3** — a free program that runs the script. Most Macs already have it.
   We'll check in a moment.
3. **A Readwise account**, if you want to import the result (a free trial works).

---

## Step 1 — Make sure Python is installed

Python is the engine that runs this tool. Let's check whether you already have it.

### On a Mac
1. Open the **Terminal**: press `Cmd (⌘) + Space`, type `Terminal`, and press Enter.
   A small window with text appears — this is where you'll type commands.
2. Type this and press Enter:
   ```
   python3 --version
   ```
3. If you see something like `Python 3.11.5`, you're set — skip to Step 2.
   If you see *"command not found,"* install Python from
   [python.org/downloads](https://www.python.org/downloads/) (click the big
   yellow **Download** button, open the file, and follow the prompts).

### On Windows
1. Open the **Start menu**, type `PowerShell`, and press Enter.
2. Type `python --version` and press Enter.
3. If you don't see a version number, install Python from
   [python.org/downloads](https://www.python.org/downloads/).
   **Important:** on the first screen of the installer, check the box that says
   **"Add Python to PATH"** before clicking Install.

> Nothing else needs to be installed — this tool only uses parts that come with Python.

---

## Step 2 — Download the script

Save the file **`logos_to_readwise.py`** somewhere easy to find, like your
**Desktop**.

> *These instructions assume the file is named `logos_to_readwise.py`. If yours
> has a different name, just use that name wherever you see it below. Tip: keep
> the name simple — avoid spaces and parentheses, which can confuse the Terminal.*

---

## Step 3 — Run the tool

1. Open the Terminal (Mac) or PowerShell (Windows) as you did in Step 1.
2. Tell it to look on your Desktop by typing this and pressing Enter:
   ```
   cd ~/Desktop
   ```
   *(If you saved the script in your Downloads folder instead, type
   `cd ~/Downloads`.)*
3. Now start the tool:
   - **Mac:** `python3 logos_to_readwise.py`
   - **Windows:** `python logos_to_readwise.py`

The tool will then ask you a few simple questions. Press **Enter** to accept the
suggested answer shown in brackets, or type your choice and press Enter.

---

## Step 4 — Answering the questions

The tool asks these, in order. When in doubt, just press **Enter**.

**HOWEVER** if you attach a highlight export file, your answers to the remaining questions must match the parameters of that file, specifically `Notebook` and ` Date range`.

| Question | What it means | Easy answer |
|---|---|---|
| **Highlight export file** | An optional file that lets the tool fill in the actual highlighted passages. | Press **Enter** to skip the first time. (See the section below to use it.) |
| **Include tags?** | Whether to add your Logos tags to each note. | Press **Enter** for yes. |
| **Title** | Whether to label rows by the **notebook** name or the **book** name. | Press **Enter** for notebook. |
| **Which notes to include** | Highlights, notes, or both. | Press **Enter** for all. |
| **Date range** | Only export notes between two dates. | Press **Enter** to include everything. |
| **Notebook** | Which Logos notebook to export. It lists them with numbers. | Type the number of the notebook you want. |
| **Save location** | Where to save the finished file. | Press **Enter** to save to your Desktop. |

When it finishes, you'll see a message like:

```
Wrote 354 highlights to /Users/you/Desktop/logos_readwise.csv
```

That `logos_readwise.csv` file on your Desktop is your export. 🎉

---

## Step 5 — Import into Readwise

1. Go to **[readwise.io/import_bulk](https://readwise.io/import_bulk)** and sign in.
2. Upload the `logos_readwise.csv` file from your Desktop.
3. Readwise will add your notes and highlights to your library.

### A note about tags
Readwise sometimes does **not** turn the `.tags` into real tags during a CSV
import. If that happens, open one of the imported highlights in Readwise, make a
tiny edit to its note, and save — Readwise will then recognize the whole tag line.
This is a Readwise quirk, not something the tool can change. If you'd rather not
see the tag line at all, answer **no** to the "Include tags?" question.

---

## Optional — Recovering the highlighted text

Logos stores your **notes**, but it does **not** store the **text you
highlighted** in a place this tool can read — it only keeps a pointer to the spot
in the book. So by default, a highlight shows up as a *link* to the passage rather
than the passage itself.

You can recover the actual highlighted sentences with one extra step:

1. In Logos, open the notebook you want to export.
2. Sort the notes by **Date Created** (this is Logos's standard order).
3. **Export the notebook as plain text** (a `.txt` file) and save it to your
   Desktop. *(In Logos: the notebook's menu → Print/Export → choose a plain-text
   or document format.)*
4. Run the tool again. When it asks for the **Highlight export file**, type the
   path to that file, for example:
   ```
   ~/Desktop/My Notebook.txt
   ```
   *(Tip: you can drag the file from your Desktop into the Terminal window and it
   will fill in the path for you.)*

The tool then matches each note to its passage and places the highlighted text at
the top of the row.

### How reliable is this?
- For highlights **that have a note**, the match is based on your note's exact
  words — **very accurate**.
- For highlights **with no note**, the tool lines them up by their order in the
  export. This is usually correct, but because it relies on order, it's worth
  **glancing over a few** of those after importing. The tool prints a summary and
  a warning if the counts don't line up perfectly.

> Make sure you export the **same notebook** you're exporting with the tool, and
> leave it sorted by Date Created, so the two line up.

---

## Troubleshooting

**"command not found: python3" (or "python")**
Python isn't installed or wasn't added to PATH. Re-do [Step 1](#step-1--make-sure-python-is-installed).
On Windows, make sure you checked "Add Python to PATH" during install.

**"Could not find notestool.db"**
The tool couldn't locate your Logos notes automatically. This usually means Logos
is installed in a non-standard place. You can point the tool at the file directly:
```
python3 logos_to_readwise.py --db "/full/path/to/notestool.db"
```

**The file name has spaces and the Terminal complains**
Wrap names with spaces in quotes, e.g. `"My Notebook.txt"`. Or drag the file into
the Terminal window to insert its path automatically.

**Nothing was exported**
You may have picked a notebook or date range with no matching notes. Run it again
and press Enter at each prompt to include everything.

---

## For the curious — how it works

- It opens Logos's notes database **read-only** (it never modifies your data) and
  reads your notes, tags, anchors, and dates.
- It converts Logos's rich-text formatting into Markdown (bold, italics, bullets,
  links) and cleans up stray invisible characters that can appear around Hebrew
  and Greek text.
- For book highlights it builds a precise `ref.ly` link to the exact position.
- The optional highlighted-text recovery matches your manual export back to each
  note to fill in the passages.

Everything uses only what comes built into Python — no extra downloads.

---

## Privacy & safety

- Runs entirely on your computer.
- Opens your Logos databases **read-only** — your notes are never altered.
- Sends nothing over the internet. The only file it creates is the CSV you asked for.

---

## Credits

Inspired by the excellent
[agape-apps/Logos-Notes-Exporter](https://github.com/agape-apps/Logos-Notes-Exporter).
Built for the Logos + Readwise community. Use it freely.
