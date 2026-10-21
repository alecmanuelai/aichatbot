# Learning StudyBuddy, one layer at a time

Begin by running Offline Demo. Then trace one question through the source rather
than memorizing every file. A class groups related data and methods; an object is
one instance of a class. StudyBuddy uses a few small classes with clear jobs.

## 1. Python and VS Code setup

Open the directory containing `main.py`. The repository is named `aichatbot`, but
the app is named StudyBuddy. No extra nested folder is needed. On Windows:

```powershell
py --version
py -m tkinter
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe main.py
```

Create `.venv` only if it is absent. Close the Tk test window before proceeding.
A virtual environment isolates packages; it does not uninstall or replace your
Python. Select `.venv\Scripts\python.exe` in VS Code. Running that executable
directly avoids PowerShell activation issues. If Windows' `python` command opens
the Store, use `py` for creation and the explicit `.venv` executable afterward.

The completed app was checked on Linux Python 3.12.14 / Tk 9.0.4. Your earlier
export records a basic dependency/window check on Windows Python 3.14.7; run this
finished app's tests on that installation before the presentation.

## 2. Project folders

Read `main.py` first: `main()` loads configuration, creates the database and
services, constructs the window, and enters `mainloop()`. Startup errors use safe
messages. `config.py` defines `AppConfig`, `PROJECT_DIR`, and the 4,000-character
limit. Paths use `__file__`, so changing the terminal directory does not create
a second database accidentally.

`ui/` contains three widgets: `MainWindow` coordinates the app, `ChatPanel` renders
messages and input, and `Sidebar` renders navigation. `backend/` has
`ChatbotService` for a send/reply operation, `AIService` for responses, and
`ConversationService` for history. `database/` contains `DatabaseManager`.
Each `__init__.py` identifies a Python package and briefly describes it.

`tests/test_database.py`, `test_config.py`, `test_ai_service.py`, and
`test_chatbot_service.py` check those layers; `tests/gui_smoke.py` exercises actual
widgets. `docs/` explains the code and demonstration. `data/` and `.venv/` are
generated local state. `.env.example` shows configuration names; `.gitignore`
keeps `.env`, dependencies, caches, and databases out of Git.

## 3. Dependencies

`requirements.txt` pins CustomTkinter (desktop widgets), python-dotenv (local
configuration), and requests (HTTPS), plus their transitive packages. `pip check`
detects incompatible installed requirements. Do not install `sqlite3` or `tkinter`
with pip: they are supplied by Python/your operating system. `unittest`, `queue`,
`threading`, `uuid`, and `pathlib` are also part of the standard library.

## 4. GUI

Tk is event driven. `mainloop()` waits for clicks, keys, and timers. Widget
callbacks must finish quickly so the window can repaint and respond to input.
`MainWindow` uses `grid()` for its sidebar and chat area; row/column weights allow
resizing. `ChatPanel.show_messages()` builds colored bubbles and converts UTC
timestamps to local time. Its scrollable frame keeps long histories accessible.

`ChatPanel._enter()` checks Tk's Shift modifier: Enter sends; Shift+Enter leaves
the normal newline behavior. The composer and sidebar are disabled during a
request, preventing duplicate sends and accidental chat changes. The mode badge
always identifies demo versus online responses. The input limit is checked in
the backend, so it applies independently of the GUI.

Exercise: run the app, resize it, and identify the callback for each button.

## 5. SQLite

`DatabaseManager.initialize()` creates two tables if absent. A conversation has
a UUID, title, and creation time. A message has an integer ID, conversation ID,
role, content, and timestamp. One conversation can contain many messages.

`connection()` is a context manager: it opens a connection, enables
`PRAGMA foreign_keys = ON`, commits on success, rolls back on exceptions, and
closes in `finally`. A SQLite connection belongs to its current thread. Workers
create their own short-lived connections through this method.

SQL values use `?` parameters rather than string interpolation. For example,
`get_messages()` supplies `(conversation_id,)` separately from its SQL string.
Message order is explicitly `ORDER BY id ASC`, even when timestamps are identical.
`ON DELETE CASCADE` removes messages with their conversation.

`add_user_message()` inserts a question and derives a short title from the first
question within one transaction. `add_assistant_reply()` locks before checking
the final message ID and role. It refuses stale, duplicate, or deleted-chat
replies. `BEGIN IMMEDIATE` reserves the write transaction before the check.

Exercise: find the two places that use `BEGIN IMMEDIATE` and explain why the
check and write should stay together.

## 6. Backend

`ConversationService` exposes `create()`, `list_all()`, `messages()`, and `delete()`
without requiring widgets to contain SQL. `ChatbotService.validate_message()`
rejects non-string, blank, and oversized input, then trims surrounding whitespace.

`submit_user_message()` saves the user's text once and returns the message ID.
`complete_reply()` loads the original conversation, confirms that this message
is still unanswered, obtains a response, checks cancellation, and attempts the
guarded insert. Retry calls only `complete_reply()`, so it reuses the saved ID.

Exercise: temporarily simulate an API failure in a test and count user messages
before and after retry. There should still be one question.

## 7. AI API connection

`AppConfig.load()` reads `.env` next to the project and respects existing process
variables. `validate()` checks mode, timeout, required online fields, placeholders,
and HTTPS URL structure. The key is excluded from the dataclass representation.
Never print configuration or credentials while demonstrating.

`AIService.reply()` chooses one of two explicit branches:

- Offline: keyword rules select a fixed explanation. Each starts with
  `[OFFLINE DEMO — predefined response]`. This branch does not call a model.
- Online: `build_context()` starts with a study-assistant system instruction,
  then adds history while excluding stored assistant demo answers. `requests`
  sends JSON to the configured provider using bearer authentication.

The endpoint is exactly `base_url.rstrip("/") + "/chat/completions"`. HTTPS is
mandatory, verification is enabled, redirects are rejected, and the configured
connect/read timeout is finite. Managed proxies and trusted CA bundles still
work. Error statuses become short safe messages: access rejected, quota limit,
timeout, network/TLS problem, server problem, or invalid/empty response.
An online failure never silently switches to demo mode.

Copy `.env.example` only if you have no `.env`; enter the provider's API root,
private key, and model locally, then restart. Never commit or project `.env`.
For the cleanest demonstration, use a new conversation after switching modes.

## 8. Integration

Follow the sequence in `MainWindow.send_message()` and `start_reply()`:

1. Validate and save the user's message, capturing its conversation and message IDs.
2. Refresh the history and disable affected controls.
3. Start a daemon thread running the standalone `run_reply()` function.
4. The worker uses backend/database objects and puts a result into `Queue`.
5. `poll_results()`, scheduled every 75 ms with Tk's `after()`, reads the queue
   on the GUI thread, refreshes messages, and re-enables controls.

The worker receives no widget references. It never calls Tk, including `after()`.
An `Event` marks cancellation when closing. A running HTTP request is not forcibly
killed; it is bounded by its connect/read timeout, and a canceled reply is not
normally saved after the next cancellation check. If an insert already finished
when closing, that valid answer may appear next time. The original question always
remains saved. `close()` stops scheduled callbacks before destroying widgets.

## 9. Testing

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m tests.gui_smoke
```

The backend suite uses temporary directories, real SQLite, and mocked HTTP. It
checks schema, ordering, persistence, foreign keys, cascade deletion, transactions,
validation, response labels, history construction, HTTP/transport/response errors,
safe retry, cancellation, and cross-thread database use.

The GUI suite needs a desktop display. It opens real windows, generates keyboard
events, sends offline questions, checks navigation/deletion and resizing, simulates
a delayed failure, retries after reopening, and closes during a pending request.
It does not verify a real provider, Windows display scaling, or every physical
mouse/keyboard interaction. Run the README checklist on the presentation laptop.

## 10. Presentation

Use `PRESENTATION.md` for the ten-minute script and five roles. Learn one clear
sentence for each layer, then trace one click end to end. Explain the difference
between a rule-based demo and a real external model. Prepare Offline Demo first,
keep keys off screen, and rehearse the exact questions you plan to use.

Suggested learning order: `main.py` → offline branch in `ai_service.py` →
`chatbot_service.py` → database methods → GUI callbacks and the queue → online
request handling. Make small experiments in a copy or branch and run tests after
each behavior change. You do not need to memorize the entire codebase.
