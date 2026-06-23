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

## Quick start

For those who just want to go (each step is explained in detail further down):

1. **Install Python 3** if you don't have it ([details](#step-1--make-sure-python-is-installed)).
2. **Download** `logos_to_readwise.py` to your Desktop.
3. **(Recommended) Export your highlights from Logos** so the tool can include the
   actual highlighted text: in Logos, **select every note in the notebook**, **set
   the sort to Date Created**, and **export to plain text (.txt)** on your Desktop.
4. **Open the Terminal** and run it:
   ```
   cd ~/Desktop
   python3 logos_to_readwise.py        # on Windows: python logos_to_readwise.py
   ```
5. **Answer the prompts.** First pick your notebook; then, when it asks for the
   highlight file, **drag the `.txt` from step 3 into the window**. *(Use the export
   of the same notebook — see [why](#-the-one-thing-to-get-right-keep-them-matched).)*
6. **Import** the resulting `logos_readwise.csv` at
   [readwise.io/import_bulk](https://readwise.io/import_bulk).

That's it. The rest of this page explains each step for anyone who'd like more detail.

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

The tool asks just four short questions, in this order. When in doubt, press **Enter**.

| Question | What it means | Easy answer |
|---|---|---|
| **Notebook** | Which Logos notebook to export — **one per run**. It lists them with numbers. | Type the number of the notebook you want. |
| **Highlight export file** | The `.txt` export of that notebook, so the tool can fill in the actual highlighted passages. Most people will want this. | **Drag the `.txt` file into the window** and press Enter ([details](#optional-recovering-the-highlighted-text)), or press Enter to skip. |
| **Include tags?** | Whether to add your Logos tags to each note. | Press **Enter** for yes. |
| **Save location** | Where to save the finished file. | Press **Enter** to save to your Desktop. |

> **Tip:** When asked for the highlight file, just **drag the `.txt` from your
> Desktop into the Terminal window** — the tool handles the quotes and spaces macOS
> adds. If it can't find the file, it tells you and lets you try again instead of
> skipping. Make sure it's the export of the **same notebook** you just picked.

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
Your Logos tags are placed on the first line of each note as `.tags` — the format
Readwise recognizes. After importing, Readwise may take a moment to process them
into real tags, so don't worry if they don't appear instantly. If you'd rather not
include them at all, answer **no** to the "Include tags?" question.

---

## Optional — Recovering the highlighted text

**Most people will want this step.** Logos stores your **notes**, but it does
**not** store the **text you highlighted** in a place this tool can read — it only
keeps a pointer to the spot in the book. So by default, a highlight shows up as a
*link* to the passage rather than the passage itself.

You can recover the actual highlighted sentences with one extra export:

1. In Logos, **open the notebook** you're going to export (the tool works on one
   notebook at a time — export the **whole notebook**, not a single book).
2. **Sort by Date Created** (this is Logos's standard order — leave it as is).
3. **Export the whole notebook as plain text** (a `.txt` file) and save it to your
   Desktop. *(In Logos: the notes panel menu → Print/Export → choose a plain-text or
   document format.)*
4. Run the tool. When it asks for the **Highlight export file**, type the path to
   that file, for example:
   ```
   ~/Desktop/My Notebook.txt
   ```
   *(Tip: you can drag the file from your Desktop into the Terminal window and it
   will fill in the path for you.)*

The tool then matches each note to its passage and places the highlighted text at
the top of the row.

### ⭐ The one thing to get right: keep them matched

This is the only part that needs a little care — but it's simple once you see it:

> **The Logos export and the tool must point at the same notes.**
> Export the **whole notebook** from Logos (select every note), choose that **same
> notebook** in the tool, and leave the export **sorted by Date Created**. That's
> what lets the tool line each note up with its highlighted passage.

After it runs, the tool tells you whether the export **lines up** with the notebook
(e.g. *"OK: the export lines up with this notebook (98% of text notes matched)"*).
If it doesn't look like the same set of notes — say you exported a single book
instead of the whole notebook — it prints a clear **warning** so you'll know to
re-export. It won't fail silently.

### How reliable is this?
- For highlights **that have a note**, the match is based on your note's exact
  words — **very accurate**.
- For highlights **with no note**, the tool lines them up by their order in the
  export. This is usually correct, but because it relies on order, it's worth
  **glancing over a few** of those after importing.

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

**The highlighted text didn't come through, or looks shifted**
This almost always means the Logos export and the tool weren't pointed at the same
notes. Export the **whole notebook** (not a single book), keep it **sorted by Date
Created**, and pick that same notebook when the tool asks. See
[The one thing to get right](#-the-one-thing-to-get-right-keep-them-matched).

**The file name has spaces and the Terminal complains**
Wrap names with spaces in quotes, e.g. `"My Notebook.txt"`. Or drag the file into
the Terminal window to insert its path automatically.

**Nothing was exported**
You may have picked an empty notebook. Run it again and choose a notebook that has
notes in it.

---

## For the curious — how it works

- It opens Logos's notes database **read-only** (it never modifies your data) and
  reads your notes, tags, anchors, and dates.
- It converts Logos's rich-text formatting into Markdown (bold, italics, bullets,
  links) and cleans up stray invisible characters that can appear around Hebrew
  and Greek text.
- For book highlights it builds a precise `ref.ly` link to the exact position.
- The optional highlighted-text recovery matches your manual export back to each
  note: notes with text are matched by their exact words, and the note-less
  highlights in between are filled in by order.

Everything uses only what comes built into Python — no extra downloads.

---

## Privacy & safety

- Runs entirely on your computer.
- Opens your Logos databases **read-only** — your notes are never altered.
- Sends nothing over the internet. The only file it creates is the CSV you asked for.

---

## Credits
[Acts 17.11](https://ref.ly/Acts.17.11) and [James 1.22](https://ref.ly/Jas.1.22)
Inspired by the excellent
[agape-apps/Logos-Notes-Exporter](https://github.com/agape-apps/Logos-Notes-Exporter).
Built for the Logos + Readwise community. Use it freely.  
