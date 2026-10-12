# Setup

One-time setup for the capstone project, about 20 minutes. It installs everything every
checkpoint needs; nothing new is installed later.

## 1. Editor

Use **Cursor** or **VS Code** (Visual Studio Code). Visual Studio, without "Code", is a
different product. Both editors read this project's `.vscode/settings.json`, and both
need the Python extension, which they offer to install when a `.py` file is opened.

## 2. Python 3.12

Check whether it is installed:

| macOS / Linux | Windows (PowerShell) |
|---|---|
| `python3.12 --version` | `py -3.12 --version` |

If it is missing, install Python 3.12 from <https://www.python.org/downloads/>. On
Windows, tick **Add python.exe to PATH** in the installer. On macOS, Homebrew also works:
`brew install python@3.12`.

On macOS, typing `python3` may start Apple's own Python 3.9 (`/usr/bin/python3`). The
course does not use it; the next step creates the environment with `python3.12`
explicitly.

## 3. Virtual environment

A virtual environment is a folder, `.venv`, holding this project's own Python and
packages, separate from the rest of the computer. In a terminal opened in this project
folder:

| macOS / Linux | Windows (PowerShell) |
|---|---|
| `python3.12 -m venv .venv` | `py -3.12 -m venv .venv` |
| `source .venv/bin/activate` | `.venv\Scripts\activate` |

The prompt now starts with `(.venv)`. Confirm that `python` is the environment's own:

| macOS / Linux | Windows |
|---|---|
| `which python` ends in `.venv/bin/python` | `where python` lists `...\.venv\Scripts\python.exe` first |

Activate the environment again in every new terminal. On Windows, if activation is
blocked by an execution policy, run once:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

## 4. Install

```
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

`requirements.txt` pins every package to a version tested together, so the installs on
every computer match. `pip install -e .` installs this project's library, `ragkit`, in
editable mode: every script can `import ragkit` from any folder, and changes to the
files in `ragkit/` take effect immediately.

## 5. Settings (.env) and folders

Copy `.env.example` to `.env` (same folder) and fill it in:

| Setting | Value |
|---|---|
| `OPENROUTER_API_KEY` | the key provided for the course |
| `RAG_SCENARIO` | `wikipedia` or `papers`: the capstone scenario chosen in Checkpoint 1 |
| `RAG_CORPUS_DIR` | the full path of the folder holding that scenario's documents |
| `RAG_WORK_DIR` | where logs, reports, indexes, and question sets go; keep it outside the project folder, so it survives moving to a newer checkpoint folder. Empty means a `rag_course_work` folder in the home folder |

`.env` holds a secret: never share or commit it. `.gitignore` already excludes it.

## 6. Check

```
python check_setup.py
```

Fix the first `[FAIL]` line, then run it again, until it ends with `Setup complete`. It
makes one tiny chat call and one embedding call (a fraction of a cent);
`python check_setup.py --offline` skips them.

## 7. Editor interpreter

Command Palette (Cmd+Shift+P on macOS, Ctrl+Shift+P on Windows) → **Python: Select
Interpreter** → the one inside `.venv`. The editor's Run button and test panel then use
the environment too.

## 8. Tests (optional)

```
pytest
```

Runs the project's offline tests: no API calls, no cost. On a working setup they all pass.

## Troubleshooting

| Message | Cause | Fix |
|---|---|---|
| `command not found: python3.12`, or `No suitable Python runtime found` | Python 3.12 is not installed | Step 2 |
| `ModuleNotFoundError: No module named 'langchain_openai'` (or another package) | The environment is not active, or the packages are not installed | Activate `.venv` (step 3), then `pip install -r requirements.txt` |
| `ModuleNotFoundError: No module named 'ragkit'` | The editable install was not run in this folder | `pip install -e .` in the project folder |
| `OPENROUTER_API_KEY is not set` | `.env` is missing, or its key line is empty | Step 5 |
| `401` or `User not found` from OpenRouter | The key is wrong or revoked | Copy the key into `.env` again |
| `429` or "rate limit" | Too many requests at once | Wait a minute; the library already retries 3 times |
| `402`, "requires more credits, or fewer max_tokens" | The key's remaining credit is low: OpenRouter reserves credit for the longest possible reply before each call | Ask for more credit on the key; check what is left at <https://openrouter.ai/settings/keys> |
| Packages fail to build during install | The environment uses another Python (for example 3.13 or 3.9) | Delete `.venv` and redo step 3 with Python 3.12 |
| The editor underlines imports, but scripts run | The editor uses another interpreter | Step 7 |
