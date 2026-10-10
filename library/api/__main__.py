"""Run the REST API with ``python -m library.api`` (http://127.0.0.1:5000).

Environment variables: ``LIBRARY_DB_PATH`` (default ``library.db``),
``LIBRARY_EMPLOYEE_ID`` and ``LIBRARY_API_PORT`` (default 5000).
"""

import os

from library.api.app import create_app
from library.config import DB_PATH_ENV_VAR, DEFAULT_DB_PATH, load_settings
from library.logging_config import configure_logging
from library.services.library_service import LibraryService
from library.storage.sqlite_storage import SQLiteStorage

configure_logging()
with SQLiteStorage(os.environ.get(DB_PATH_ENV_VAR, DEFAULT_DB_PATH)) as storage:
    app = create_app(LibraryService.from_storage(storage, load_settings()))
    # Single-threaded: one SQLite connection is shared by all requests.
    app.run(port=int(os.environ.get("LIBRARY_API_PORT", "5000")), threaded=False)
