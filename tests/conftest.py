"""Sets the MySQL test database before the application is imported."""

import os

os.environ["DATABASE_URL"] = "mysql+pymysql://root:@127.0.0.1:3306/tu_comite_test?charset=utf8mb4"
