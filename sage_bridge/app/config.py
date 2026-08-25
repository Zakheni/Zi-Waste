"""Environment and write-mode settings for sage_bridge."""

import os

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv(), override=True)

API_KEY = os.getenv("API_KEY", "")
ODBC_DSN = os.getenv("ODBC_DSN", "")
DEFAULT_CURRENCY = os.getenv("BRIDGE_DEFAULT_CURRENCY", "ZAR")
ADAPTER_NAME = os.getenv("SAGE_ADAPTER", "pastel_partner")
WRITE_MODE = os.getenv("SAGE_WRITE_MODE", "odbc_guarded")  # sdkcom | odbc_guarded
BIND_HOST = os.getenv("BIND_HOST", "127.0.0.1")
BIND_PORT = int(os.getenv("BIND_PORT", "8788"))
SDKCOM_PROGID = os.getenv("SDKCOM_PROGID", "Pastel.SDK")
PASTEL_COMPANY_PATH = os.getenv("PASTEL_COMPANY_PATH", "")
PASTEL_USERNAME = os.getenv("PASTEL_USERNAME", "")
PASTEL_PASSWORD = os.getenv("PASTEL_PASSWORD", "")
