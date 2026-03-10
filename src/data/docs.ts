export interface DocPage {
  slug: string;
  title: string;
  category: string;
  content: string;
}

export const docsCategories = [
  { label: "Getting Started", items: ["introduction", "quickstart", "installation", "activation"] },
  { label: "Core Concepts", items: ["authentication", "cli-commands", "investigation-workflow"] },
  { label: "Configuration", items: ["connector-setup", "api-key-usage"] },
  { label: "Support", items: ["troubleshooting", "faq"] },
  { label: "Updates", items: ["changelog"] },
];

export const docsPages: Record<string, DocPage> = {
  introduction: {
    slug: "introduction",
    title: "Introduction",
    category: "Getting Started",
    content: `# Introduction

BugPilot is a CLI-first investigation and debugging platform built for engineers who prefer working in the terminal.

## What is BugPilot?

BugPilot combines intelligent distributed tracing, automated root cause analysis, and a powerful CLI interface to help you debug production issues faster than ever.

:::info
BugPilot requires an active account with valid API credentials to use. See the [Quickstart](/docs/quickstart) guide to get started.
:::

## Key Features

- **CLI-Native**: Investigate issues directly from your terminal
- **Distributed Tracing**: Trace errors across microservices automatically
- **Root Cause Analysis**: AI-powered analysis surfaces actionable root causes
- **Connector Ecosystem**: Integrate with GitHub, Sentry, Datadog, and more
- **Investigation History**: Every investigation is logged and searchable
- **Secure Credentials**: API key + secret authentication with audit trails

## How It Works

1. Download and install the BugPilot CLI
2. Activate with your API credentials
3. Run \`bugpilot investigate\` to start debugging
4. BugPilot traces the issue and surfaces the root cause

\`\`\`bash
$ bugpilot investigate --trace ERR-4829
⠋ Tracing error through 12 services...
✓ Root cause identified in 2.3s
\`\`\`

## Next Steps

- [Quickstart Guide](/docs/quickstart) — Get up and running in 5 minutes
- [Installation](/docs/installation) — Download and install the CLI
- [CLI Commands](/docs/cli-commands) — Full command reference`,
  },
  quickstart: {
    slug: "quickstart",
    title: "Quickstart",
    category: "Getting Started",
    content: `# Quickstart

Get up and running with BugPilot in under 5 minutes.

## Prerequisites

- A BugPilot account ([sign up here](/sign-up))
- API credentials (issued by your admin)
- macOS 12+ or Windows 10+

## Step 1: Install the CLI

**macOS (Homebrew):**
\`\`\`bash
brew install bugpilot/tap/bugpilot
\`\`\`

**Windows (Scoop):**
\`\`\`bash
scoop install bugpilot
\`\`\`

## Step 2: Activate

\`\`\`bash
bugpilot activate --key YOUR_API_KEY --secret YOUR_API_SECRET
\`\`\`

:::warning
Store your API secret securely. It is shown only once when generated.
:::

## Step 3: Run Your First Investigation

\`\`\`bash
bugpilot investigate --trace ERR-1234
\`\`\`

## Step 4: Check Status

\`\`\`bash
bugpilot status
\`\`\`

You should see:
\`\`\`
BugPilot CLI v1.0.0
Status: Activated
Account: you@company.com
\`\`\`

## Next Steps

- [CLI Commands](/docs/cli-commands) — Explore all available commands
- [Connector Setup](/docs/connector-setup) — Enrich investigations with integrations`,
  },
  installation: {
    slug: "installation",
    title: "Installation",
    category: "Getting Started",
    content: `# Installation

Download and install the BugPilot CLI on your platform.

## macOS

### Homebrew (Recommended)

\`\`\`bash
brew install bugpilot/tap/bugpilot
\`\`\`

### Direct Download

Download the \`.pkg\` installer from your [Downloads](/dashboard/downloads) page.

\`\`\`bash
# Verify installation
bugpilot --version
\`\`\`

## Windows

### Scoop (Recommended)

\`\`\`bash
scoop install bugpilot
\`\`\`

### Direct Download

Download the \`.msi\` installer from your [Downloads](/dashboard/downloads) page.

## System Requirements

| Platform | Minimum Version | Architecture |
|----------|----------------|-------------|
| macOS    | 12 (Monterey)  | Intel & Apple Silicon |
| Windows  | 10             | 64-bit |

## Updating

\`\`\`bash
# macOS
brew upgrade bugpilot

# Windows
scoop update bugpilot
\`\`\`

## Uninstalling

\`\`\`bash
# macOS
brew uninstall bugpilot

# Windows
scoop uninstall bugpilot
\`\`\``,
  },
  activation: {
    slug: "activation",
    title: "Activation",
    category: "Getting Started",
    content: `# Activation

Activate your BugPilot CLI with API credentials to start investigating.

## Getting Your Credentials

1. Sign in to your BugPilot account
2. Navigate to **API Credentials** in your dashboard
3. Your API key is displayed on the credentials page
4. Your secret was provided when credentials were generated

:::info
If you don't have credentials yet, ask your team admin to generate them from the Admin Console.
:::

## Activating the CLI

\`\`\`bash
bugpilot activate --key bp_YourAPIKeyHere --secret bps_YourSecretHere
\`\`\`

On success:
\`\`\`
✓ CLI activated successfully
  Account: you@company.com
  Key: bp_YourAPI...
\`\`\`

## Verifying Activation

\`\`\`bash
bugpilot status
\`\`\`

## Deactivating

\`\`\`bash
bugpilot deactivate
\`\`\`

## Troubleshooting Activation

- **Invalid credentials**: Double-check your API key and secret
- **Expired credentials**: Ask your admin to rotate your credentials
- **Revoked credentials**: Your admin may have revoked access`,
  },
  authentication: {
    slug: "authentication",
    title: "Authentication",
    category: "Core Concepts",
    content: `# Authentication

BugPilot uses API key + secret authentication for CLI access.

## How It Works

Every BugPilot user account can have API credentials issued by an admin:

- **API Key**: A unique identifier (prefix: \`bp_\`). Visible in your dashboard.
- **API Secret**: A private token (prefix: \`bps_\`). Shown once at generation time.

## Security Model

- Secrets are hashed at rest in the database
- Secrets are shown only once when generated or rotated
- All credential operations are logged in the audit trail
- Admins can revoke or rotate credentials at any time

:::warning
Never share your API secret. If compromised, ask your admin to rotate immediately.
:::

## Credential Lifecycle

1. **Created** — Admin generates credentials for a user
2. **Active** — User activates CLI with credentials
3. **Rotated** — Admin rotates the secret (new secret issued)
4. **Revoked** — Admin revokes credentials (CLI deactivated)`,
  },
  "cli-commands": {
    slug: "cli-commands",
    title: "CLI Commands",
    category: "Core Concepts",
    content: `# CLI Commands

Complete reference for all BugPilot CLI commands.

## Global Options

\`\`\`bash
bugpilot --version    # Show version
bugpilot --help       # Show help
bugpilot --verbose    # Enable verbose output
\`\`\`

## activate

Activate the CLI with API credentials.

\`\`\`bash
bugpilot activate --key <API_KEY> --secret <API_SECRET>
\`\`\`

## deactivate

Remove stored credentials and deactivate the CLI.

\`\`\`bash
bugpilot deactivate
\`\`\`

## status

Show current activation status and account info.

\`\`\`bash
bugpilot status
\`\`\`

## investigate

Start an investigation on an error or incident.

\`\`\`bash
bugpilot investigate --trace <ERROR_ID>
bugpilot investigate --service <SERVICE_NAME> --since 2h
bugpilot investigate --log-file /path/to/logs.txt
\`\`\`

### Options

| Flag | Description |
|------|-------------|
| \`--trace\` | Trace a specific error ID |
| \`--service\` | Filter by service name |
| \`--since\` | Time window (e.g., 1h, 30m, 2d) |
| \`--log-file\` | Analyze a local log file |
| \`--output\` | Output format: text, json |

## connectors

Manage integrations with external services.

\`\`\`bash
bugpilot connectors list
bugpilot connectors add github --token <TOKEN>
bugpilot connectors remove github
\`\`\`

## history

View past investigations.

\`\`\`bash
bugpilot history
bugpilot history --limit 20
bugpilot history show <INVESTIGATION_ID>
\`\`\``,
  },
  "investigation-workflow": {
    slug: "investigation-workflow",
    title: "Investigation Workflow",
    category: "Core Concepts",
    content: `# Investigation Workflow

Learn how BugPilot investigations work from start to finish.

## Starting an Investigation

\`\`\`bash
bugpilot investigate --trace ERR-4829
\`\`\`

## What Happens

1. **Trace Collection** — BugPilot collects distributed traces related to the error
2. **Log Analysis** — Relevant logs are gathered and analyzed
3. **Root Cause Analysis** — AI identifies the most likely root cause
4. **Fix Suggestions** — Actionable fix suggestions are generated

## Reading Results

\`\`\`
→ NullPointerException at UserService.java:142
  Caused by: missing null check on user.preferences
  First seen: 2h ago | Affected: 847 requests

  Suggested fixes:
  1. Add null check before accessing user.preferences
  2. Set default value for preferences in User model
  3. Add input validation in API endpoint
\`\`\`

## Sharing Investigations

\`\`\`bash
bugpilot history show INV-123 --share
\`\`\`

This generates a shareable link for your team.`,
  },
  "connector-setup": {
    slug: "connector-setup",
    title: "Connector Setup",
    category: "Configuration",
    content: `# Connector Setup

Connect BugPilot to your existing tools to enrich investigations.

## Available Connectors

| Connector | Description |
|-----------|-------------|
| GitHub | Link commits, PRs, and issues to investigations |
| Sentry | Import error data and stack traces |
| Datadog | Pull metrics and APM data |
| PagerDuty | Correlate incidents with investigations |
| Slack | Send investigation results to channels |

## Adding a Connector

\`\`\`bash
bugpilot connectors add github --token ghp_YourTokenHere
\`\`\`

## Listing Connectors

\`\`\`bash
bugpilot connectors list
\`\`\`

## Removing a Connector

\`\`\`bash
bugpilot connectors remove github
\`\`\`

:::info
Connector tokens are stored locally in your BugPilot configuration directory and are never sent to BugPilot servers.
:::`,
  },
  "api-key-usage": {
    slug: "api-key-usage",
    title: "API Key & Secret Usage",
    category: "Configuration",
    content: `# API Key & Secret Usage

Understand how BugPilot API credentials work.

## Credential Format

- **API Key**: \`bp_\` followed by 32 alphanumeric characters
- **Secret**: \`bps_\` followed by 32 alphanumeric characters

## Where Credentials Are Used

Credentials are used exclusively for CLI activation:

\`\`\`bash
bugpilot activate --key bp_abc123... --secret bps_xyz789...
\`\`\`

## Storage

After activation, credentials are stored in:
- **macOS**: \`~/.bugpilot/credentials\`
- **Windows**: \`%APPDATA%\\bugpilot\\credentials\`

The file is readable only by the current user (600 permissions on macOS/Linux).

## Rotation

If your secret is compromised:
1. Ask your admin to rotate credentials
2. You'll receive a new secret
3. Re-activate with the new secret

\`\`\`bash
bugpilot deactivate
bugpilot activate --key bp_abc123... --secret bps_newSecret...
\`\`\`

:::warning
After rotation, the old secret is immediately invalidated. Any CLI instances using the old secret will need to re-activate.
:::`,
  },
  troubleshooting: {
    slug: "troubleshooting",
    title: "Troubleshooting",
    category: "Support",
    content: `# Troubleshooting

Common issues and solutions for BugPilot CLI.

## CLI won't activate

**Symptoms**: \`Error: Invalid credentials\`

**Solutions**:
1. Verify your API key matches exactly (including \`bp_\` prefix)
2. Ensure your secret hasn't been rotated since you last received it
3. Check that your credentials haven't been revoked by your admin
4. Confirm your account is in "active" status

## Connection errors

**Symptoms**: \`Error: Unable to connect to BugPilot API\`

**Solutions**:
1. Check your internet connection
2. Verify no firewall is blocking outbound HTTPS
3. Try: \`bugpilot status --verbose\`

## Investigation returns no results

**Solutions**:
1. Verify the error ID exists and is correctly formatted
2. Check that your connectors are properly configured
3. Ensure the time window captures the relevant events

## Permission denied errors

\`\`\`bash
# Fix permissions on macOS/Linux
chmod 600 ~/.bugpilot/credentials
\`\`\`

## Reset everything

\`\`\`bash
bugpilot deactivate
rm -rf ~/.bugpilot
bugpilot activate --key <KEY> --secret <SECRET>
\`\`\``,
  },
  faq: {
    slug: "faq",
    title: "FAQ",
    category: "Support",
    content: `# Frequently Asked Questions

## General

### What is BugPilot?
BugPilot is a CLI-first investigation and debugging platform for engineers. It helps you trace, analyze, and resolve production issues directly from your terminal.

### Do I need an account to use BugPilot?
Yes. You need a BugPilot account with valid API credentials issued by your admin.

### What platforms are supported?
macOS 12+ (Intel & Apple Silicon) and Windows 10+ (64-bit).

## Credentials

### How do I get API credentials?
Your team admin generates credentials for you from the Admin Console. You'll receive an API key (visible in your dashboard) and a secret (shown once at generation time).

### I lost my secret. What do I do?
Ask your admin to rotate your credentials. A new secret will be generated.

### Can I generate my own credentials?
No. Credentials are issued by admins only, for security and audit purposes.

## CLI

### How do I update the CLI?
Use your package manager: \`brew upgrade bugpilot\` (macOS) or \`scoop update bugpilot\` (Windows).

### Where are my credentials stored locally?
\`~/.bugpilot/credentials\` on macOS, \`%APPDATA%\\bugpilot\\credentials\` on Windows.

### Can I use BugPilot on Linux?
Linux support is planned for a future release.`,
  },
  changelog: {
    slug: "changelog",
    title: "Changelog",
    category: "Updates",
    content: `# Changelog

All notable changes to BugPilot CLI.

## v1.0.0 — 2026-03-01

### Added
- Initial public release
- CLI-first investigation workflow
- Distributed tracing across microservices
- Automated root cause analysis
- Connector support: GitHub, Sentry, Datadog, PagerDuty, Slack
- Investigation history and sharing
- API key + secret authentication
- macOS and Windows support

### Security
- Credential hashing at rest
- Audit logging for all credential operations
- Scoped file permissions for local credential storage

---

## v0.9.0-beta — 2026-02-01

### Added
- Beta release for early access users
- Core investigation command
- Basic connector framework
- Activation flow

### Fixed
- Improved error messages for connection failures
- Better handling of large log files`,
  },
};

export function getDocPage(slug: string): DocPage | undefined {
  return docsPages[slug];
}

export function getAdjacentPages(slug: string): { prev?: DocPage; next?: DocPage } {
  const allSlugs = docsCategories.flatMap((c) => c.items);
  const idx = allSlugs.indexOf(slug);
  return {
    prev: idx > 0 ? docsPages[allSlugs[idx - 1]] : undefined,
    next: idx < allSlugs.length - 1 ? docsPages[allSlugs[idx + 1]] : undefined,
  };
}
