# BugPilot CLI

CLI-first developer tool for debugging production incidents.

## Installation

```bash
pip install bugpilot
```

Or download a pre-built binary from the [releases page](https://github.com/skonlabs/bugpilot/releases).

## Quick Start

```bash
bugpilot auth activate --key YOUR_API_KEY
bugpilot incident open --title "Login failures" --severity high
bugpilot investigate start
```

## Documentation

See the [full documentation](https://github.com/skonlabs/bugpilot/tree/main/src/docs) for all commands and configuration options.
