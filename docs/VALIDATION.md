# Validation record

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
