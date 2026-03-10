# BugPilot

A paid, CLI-first debugging and investigation platform.

**Core user journey:** symptom → evidence → timeline → hypotheses → safest next action

## Quick Start

```bash
# Start backend + database
docker-compose up -d

# Install CLI
cd cli && pip install -e .

# Activate license
bugpilot auth activate
```

See [docs/developer_setup.md](docs/developer_setup.md) for full setup instructions.
