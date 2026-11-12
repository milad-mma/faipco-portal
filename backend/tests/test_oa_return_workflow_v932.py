"""v9.3.2: integration of returned-letter cartable queries using local SQLite.

The isolated subprocess avoids needing production asyncpg, storage or .env in
an offline test runner. The real service query methods and ORM model columns
are executed against SQLite; PostgreSQL staging must still be verified.
"""
from pathlib import Path
import os
import subprocess
import sys


def test_return_for_revision_is_actionable_and_not_an_ordinary_draft():
    backend = Path(__file__).resolve().parents[1]
    script = backend / 'tests' / 'oa_return_scenarios_v932.py'
    env = os.environ.copy()
    env['PYTHONPATH'] = str(backend)
    result = subprocess.run(
        [sys.executable, str(script)], cwd=str(backend), env=env,
        text=True, capture_output=True, timeout=25, check=False,
    )
    assert result.returncode == 0, result.stdout + '\n' + result.stderr
    assert 'all assertions passed' in result.stdout
