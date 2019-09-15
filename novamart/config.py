"""Runtime configuration from environment."""
import os

DSN = os.environ.get("NOVAMART_DSN", "host=/tmp/novamart_pg dbname=novamart user=novamart")
LOG_DIR = os.environ.get("NOVAMART_LOG_DIR", "./logs")
POOL_MAX = int(os.environ.get("NOVAMART_POOL_MAX", "22"))
