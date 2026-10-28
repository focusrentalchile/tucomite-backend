"""Sets the MySQL test database before the application is imported."""

import os

os.environ["DATABASE_URL"] = "mysql+pymysql://root:@127.0.0.1:3306/tu_comite_test?charset=utf8mb4"

from app.main import app as _app  # noqa: E402, F401
from tests.helpers.platform_accounts import ensure_test_platform_accounts  # noqa: E402

ensure_test_platform_accounts()
