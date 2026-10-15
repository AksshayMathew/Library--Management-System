"""Run the REST API with ``python -m library.api`` (http://127.0.0.1:5000).

On start-up it welcomes the user and asks for their Employee ID, which sets
the personalised rules for every request this server handles.
Environment variables: ``LIBRARY_DB_PATH`` (default ``library.db``) and
``LIBRARY_API_PORT`` (default 5000).
"""

import os
import sys

from library.api.app import create_app
from library.config import DB_PATH_ENV_VAR, DEFAULT_DB_PATH, load_settings
from library.exceptions import LibraryError
from library.logging_config import configure_logging
from library.services.library_service import LibraryService
from library.startup import WELCOME_MESSAGE, ask_employee_id, describe_rules
from library.storage.sqlite_storage import SQLiteStorage

configure_logging()
print(WELCOME_MESSAGE)
try:
    settings = load_settings(ask_employee_id())
    storage = SQLiteStorage(os.environ.get(DB_PATH_ENV_VAR, DEFAULT_DB_PATH))
except LibraryError as exc:
    print(f"Error: {exc}", file=sys.stderr)
    sys.exit(1)

print(describe_rules(settings))
with storage:
    app = create_app(LibraryService.from_storage(storage, settings))
    # Single-threaded: one SQLite connection is shared by all requests.
    app.run(port=int(os.environ.get("LIBRARY_API_PORT", "5000")), threaded=False)
