# Validation record

## UI refresh — 22 October 2026

Validated with Linux Python 3.12.14, Tk 9.0.4, and CustomTkinter 5.2.2:

- All 46 backend/configuration/diagnostic tests passed.
- All five real-window GUI scenarios passed with temporary databases and no
  live provider calls. Existing send, retry, history, delete, and shutdown
  scenarios remain covered.
- New GUI checks cover starter prompts filling drafts without sending, the
  character limit, full-reply clipboard copying, keyboard-driven conversation
  search, and clearing a search when starting a chat.
- Long paragraphs and unbroken identifiers were checked at 860×580 and
  1100×760 logical window sizes, at 100%, 125%, and 150% display scaling.
  Tests verify actual window dimensions, text bounds, the reachable final line,
  composer/footer bounds, and hidden status controls across DPI changes.
- Inspected welcome, conversation, and smaller-window screenshots on Xorg.
  The committed preview contains sample messages, not a live model response.

Two clipping causes were fixed: physical pixel widths were being scaled again
when used as label wrap lengths, and a resize binding was replacing the
scrollable frame's own scroll-region handler. Hidden status controls now stay
hidden when DPI changes. The restricted Xorg environment uses Arial aliases
and fallback shape drawing; Windows uses Segoe UI and still needs a local
visual check of this refreshed version.

The user supplied screenshots of successful Gemini replies before this UI
refresh. This update changes only presentation and navigation, and adds no
dependencies or changes to provider settings, credentials, or stored history.

## Original application — 21 October 2026

The completed application was validated in the cloud workspace on 21 October
2026. Runtime: Linux, Python 3.12.14, Tk 9.0.4, CustomTkinter 5.2.2, SQLite 3.53.1.

| Check | Result |
| --- | --- |
| Install pinned requirements into project `.venv` | Passed; rerunning installation reused the installed versions |
| `python -m pip check` in `.venv` | Passed; no broken requirements |
| `python -m unittest discover -s tests -v` | 25 tests passed; none skipped |
| `DISPLAY=:91 python -m tests.gui_smoke` | Three real-window scenarios passed; none skipped |
| Compile application and test Python files | Passed |
| Visual inspection on virtual Xorg display | Checked layout, mode badge, messages, composer, and sidebar; corrected a font fallback issue |

All Python commands above used `.venv/bin/python`. Backend tests used temporary
SQLite databases. API tests mocked `requests.Session`; no credentials or paid
requests were used. The GUI tests used a dummy Xorg display, real CustomTkinter
windows, and temporary databases.

The GUI scenarios exercised blank-message feedback, Shift+Enter versus Enter,
an offline response, resizing, new/select/delete chat, deletion cancellation,
disabled controls during a delayed request, duplicate-submit prevention, an API
failure, reopening saved history, retry without duplicate questions, and both
canceling and confirming closure during a pending request. Shutdown was corrected
to cancel pending GUI timers; the final run had no stale-callback errors.

This restricted cloud home directory does not let CustomTkinter populate
`~/.fonts`. It prints a font-loader warning and falls back to circle-based widget
drawing. Explicit Arial/Tk font aliases keep text scalable. This did not prevent
the functional checks, but Windows rendering and display scaling still need the
README's manual checklist on the presentation laptop.

The supplied earlier conversation reports a basic CustomTkinter compatibility
check on Windows Python 3.14.7. That historical result is not a current Windows
test of this completed app. A real Online AI provider request is also unverified.
Configure the provider privately and run a deliberate live request if you need to
demonstrate that mode. Mocked HTTP tests establish request/error behavior only.
