# StudyBuddy

A desktop study assistant built with Python, CustomTkinter, and SQLite. This is
the StudyBuddy implementation in the `aichatbot` / `aichatbotDP` repository.

The default **Offline Demo** runs without an account, API key, or internet.
It selects predefined explanations about Python, SQLite, APIs, algebra, and
study habits. Every demo answer is explicitly labeled. **Online AI** sends real
chat-completion requests to an external provider you configure.

## Run on Windows

Open the project folder in VS Code. Use the terminal in the folder containing
`main.py` (the folder may be named `aichatbot` or `studybuddy`; do not nest another
project folder inside it).

```powershell
py --version
py -m tkinter
# Create this only if .venv does not already exist:
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pip check
.venv\Scripts\python.exe main.py
```

Close the Tk test window before continuing. These commands require no virtual
environment activation, so PowerShell's activation-script policy is irrelevant.
In VS Code, select `.venv\Scripts\python.exe` using **Python: Select Interpreter**.
Keep your existing Python installation. Python 3.12 or newer is recommended.
The current build was tested on Linux Python 3.12.14 and Tk 9.0.4. The supplied
earlier session reports a basic CustomTkinter check on Windows Python 3.14.7;
this completed application still needs a manual check on your Windows machine.

On a Linux desktop:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

Tkinter and SQLite come from Python/the OS, **not pip**. Linux distributions may
need their `python3-tk` and `python3-venv` packages. A graphical display is required
for the desktop window; the backend tests can run without one.

## Using the app

- Ask a question and press Enter or click Send. Shift+Enter inserts a newline.
- Messages are limited to **4,000 characters after trimming surrounding whitespace**.
- The sidebar restores saved conversations. New Chat starts another; Delete Chat
  asks before deleting the selected conversation and all its messages.
- During a request, the sidebar and composer are disabled while the window stays
  responsive. A loading bar shows progress. Closing prompts if a request is running.
- On failure, your question stays saved. **Retry reply** reuses that question;
  it does not insert a duplicate. Retry it, or create/select another chat.
- An unanswered question remains retryable after restarting. A successful reply
  may already be saved if it finished just before you closed the window.
- Timestamps are stored in UTC and displayed in your computer's local timezone.

History lives in `data/studybuddy.db`, relative to the project, regardless of the
terminal's working directory. The database is local plaintext; keep private study
content on a trusted machine. Back it up while the app is closed if needed.

## Configure Online AI

Offline mode needs no `.env`. To enable online mode, copy `.env.example` to `.env`
**only if `.env` does not already exist**. Enter values locally; never share the
key in chat, screenshots, commits, or presentation slides.

```dotenv
AI_MODE=online
AI_BASE_URL=https://your-provider.example/v1
AI_API_KEY=your_private_key_here
AI_MODEL=your_provider_model_name
AI_TIMEOUT_SECONDS=30
```

Use your provider's documented **OpenAI-compatible chat completions** API root
and model. `AI_BASE_URL.rstrip("/") + "/chat/completions"` constructs the endpoint.
For example, `https://api.example.com/v1/` becomes
`https://api.example.com/v1/chat/completions`. Include `/v1` if your provider
requires it; do not include `/chat/completions` in the base URL.

HTTPS is required. Certificate verification stays enabled, and redirects are
rejected. Existing HTTPS proxy and certificate-bundle settings are honored;
`.netrc` authentication does not replace your configured key. Requests has a
connect/read timeout of 1–120 seconds (default 30), not a total elapsed-time
deadline. The app never prints the key or provider error response bodies.

Restart after changing `.env`. Exported environment variables take precedence
over `.env`. The badge shows the selected mode. Online failures show an error;
they never silently become demo answers. Online context includes a study-assistant
system instruction and the saved user/assistant history, **excluding assistant
answers with the offline-demo prefix**. Previous user questions remain in context.
Start a fresh chat when changing modes for the clearest presentation.

Only press Send in Online AI when you intend to send that conversation's context
to your provider; its usage may cost money. No live provider request was made
during this implementation. Credentials and provider-specific compatibility
remain for you to verify locally.

## Tests

From the project root on Windows:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m tests.gui_smoke
```

On Linux, replace `.venv\Scripts\python.exe` with `.venv/bin/python`.
The first command runs 41 backend/configuration/diagnostic tests without a display.
The second opens real windows and runs three GUI scenarios; it needs a display.
All tests use temporary databases. HTTP responses are mocked; tests never need
credentials or make paid requests. See [validation results](docs/VALIDATION.md).

Manual Windows checks before presenting:

1. Resize the window; confirm bubbles, timestamps, scrolling, and text remain readable.
2. Ask “Explain Python classes”; verify the offline badge and labeled answer.
3. Try Enter, Shift+Enter, and Send; reject blank or overly long messages.
4. Create two chats, switch between them, restart, and verify saved history.
5. Cancel a deletion, then confirm one; verify the other chat remains intact.
6. With an intentionally unavailable provider in Online AI, verify an error and
   retry without duplicating the question. Restore your valid settings afterward.
7. With your own configured provider, check a real answer and a follow-up. Never
   claim this step passed based only on offline or mocked tests.

## Project map

| File or folder | Responsibility |
| --- | --- |
| `main.py` | Connect the services, start the window, and handle startup errors |
| `config.py` | Load and validate `.env`; define the project path and message limit |
| `check_online.py` | Check Gemini connectivity and models; optionally test one chat reply |
| `ui/main_window.py` | Coordinate events, worker threads, retries, and queue polling |
| `ui/chat_panel.py` | Render bubbles, timestamps, input, mode, and status |
| `ui/sidebar.py` | Render chat navigation and new/delete controls |
| `backend/chatbot_service.py` | Validate/save a question and attach its reply safely |
| `backend/ai_service.py` | Labeled offline responses and verified HTTPS requests |
| `backend/conversation_service.py` | Simple interface for conversation operations |
| `database/database_manager.py` | Tables, transactions, queries, and connection cleanup |
| `ui/`, `backend/`, `database/` `__init__.py` | Mark the directories as Python packages |
| `tests/` | Database, configuration, backend, API, and desktop tests |
| `data/` | Generated local database, ignored by Git |
| `.env.example` | Placeholder configuration to copy locally |
| `.gitignore` | Excludes secrets, virtual environments, caches, and runtime databases |
| `requirements.txt` | Pinned application dependencies |
| `docs/` | Learning guide, presentation notes, and validation record |

Start with the [learning guide](docs/LEARNING_GUIDE.md), then rehearse the
[five-person presentation](docs/PRESENTATION.md). Source files are authoritative.

## Troubleshooting

For a Gemini timeout or model-access problem, close the desktop app and run this
from the project folder in PowerShell:

```powershell
.\.venv\Scripts\python.exe .\check_online.py
```

This reads your existing `.env`, uses verified HTTPS and the same bearer
authentication as the app, and requests only Gemini's model list. It reports
connection/read timeouts, access errors, and model availability without printing
your key or raw response bodies. By default it sends no chat-generation request.
A successful model listing does not establish chat quota or a successful answer.
Model names should come from the models available to your Google project.

If model listing succeeds but chat fails, explicitly test generation:

```powershell
.\.venv\Scripts\python.exe .\check_online.py --chat
```

This sends one short test message using your configured model and can consume API
quota. It uses the same payload format as a new StudyBuddy chat and does not read
or send saved conversations. It reports the HTTP status and recognized error
categories using fixed explanations; raw error text and generated replies are
not printed. A successful test confirms one chat reply with the current settings.

| Symptom | What to do |
| --- | --- |
| `python` opens the Microsoft Store | Use `py` to create the environment, then its explicit executable above |
| Import error for CustomTkinter/requests/dotenv | Install with `.venv\Scripts\python.exe -m pip install -r requirements.txt`; select that interpreter in VS Code |
| Missing Tk | Check `py -m tkinter`; enable Tcl/Tk in your Python installer, or install the OS Tk package on Linux |
| “A desktop display with Tk is required” | Run locally on a desktop, or supply a virtual display for automated GUI tests |
| Linux font-cache warning | CustomTkinter expects a writable `~/.fonts`; restricted containers may use fallback drawing. See validation notes |
| Online configuration rejected | Replace placeholders, use an HTTPS root, and supply the provider's exact model name |
| Access rejected / quota / server error | Check permissions, balance, or provider status; then click Retry reply |
| TLS verification failure | Check the clock, trusted certificate setup, and managed proxy configuration; keep verification enabled |
| Database unavailable | Check disk space and project-folder permissions; avoid running two instances or syncing a live database |
| Question has no answer after restarting | Click Retry reply, or start a new chat; the saved question is preserved |
