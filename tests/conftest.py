"""Repository-wide test-process isolation from developer-local configuration."""

import os

# Tests provide every setting they need explicitly. A developer's ignored `.env`
# must never enable providers, inject credentials, or change policy under the suite.
os.environ.setdefault("DM_DISABLE_DOTENV", "1")
