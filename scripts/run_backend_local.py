"""Local backend launcher: loads .env, forces the Postgres backend, runs uvicorn.

Kept as a file (not an inline -c string) so the exact environment contract is
reviewable and so a silent process death is visible in a restart-loop log.
"""

import os
import sys

# Script mode puts scripts/ first on sys.path; the uvicorn import string
# "main:app" resolves against the repo root, so add it explicitly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

os.environ.setdefault("QMA_STORAGE_BACKEND", "postgres")
# The traction swarm legitimately polls invoice status from one IP while
# several buyer instances run; the shared default (20/min) trips 429s that
# waste the buyers' bounded poll windows. Local operator allowance only.
os.environ.setdefault("QMA_RATE_LIMIT_INVOICE_PER_MIN", "60")

import uvicorn

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, log_level="info")
