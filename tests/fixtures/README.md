# Test Fixtures

These JSON files are real Qobuz API responses captured by `tests/capture_fixtures.py`.
They ground all test mocks in actual API schema so tests don't silently diverge from reality.

## When to refresh
- When tests fail due to missing/renamed fields and you suspect the API changed.
- When adding tests for a new endpoint not yet captured.

## How to refresh
Requires a valid `~/.config/qobuz-dl/config.ini`:

    python tests/capture_fixtures.py

PII (email, name, country) is automatically scrubbed before saving.
