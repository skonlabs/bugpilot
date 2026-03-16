#!/usr/bin/env python3
"""
BugPilot developer setup wizard.

Run:  python scripts/setup.py
  or: make dev-setup
"""
from __future__ import annotations

import getpass
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
TERMS_VERSION = "1.0"
TERMS_URL = "https://bugpilot.io/terms"


# ── Colours (stdlib only) ─────────────────────────────────────────────────────

def _ansi(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if sys.stdout.isatty() else text

def bold(t: str) -> str:   return _ansi("1", t)
def green(t: str) -> str:  return _ansi("32", t)
def yellow(t: str) -> str: return _ansi("33", t)
def red(t: str) -> str:    return _ansi("31", t)
def cyan(t: str) -> str:   return _ansi("36", t)
def dim(t: str) -> str:    return _ansi("2", t)


# ── UI helpers ────────────────────────────────────────────────────────────────

def header(title: str) -> None:
    print()
    print(bold("━" * 58))
    print(bold(f"  {title}"))
    print(bold("━" * 58))

def ok(msg: str) -> None:   print(f"  {green('✓')}  {msg}")
def fail(msg: str) -> None: print(f"  {red('✗')}  {msg}")
def info(msg: str) -> None: print(f"     {msg}")
def warn(msg: str) -> None: print(f"  {yellow('!')}  {msg}")
def hint(msg: str) -> None: print(f"     {dim(msg)}")

def ask(prompt: str, default: str = "", secret: bool = False) -> str:
    display = f"  {prompt}"
    if default:
        display += f"  {dim('[' + default + ']')}"
    display += ": "
    val = getpass.getpass(display) if secret else input(display).strip()
    return val or default

def confirm(prompt: str, default: bool = True) -> bool:
    hint_str = "[Y/n]" if default else "[y/N]"
    val = input(f"  {prompt} {dim(hint_str)}: ").strip().lower()
    return default if val == "" else val in ("y", "yes")

def choose(prompt: str, options: list[tuple[str, str]], default: str = "1") -> str:
    print(f"\n  {prompt}")
    for i, (_, label) in enumerate(options, 1):
        marker = bold(f"  {i})") if str(i) == default else f"  {dim(str(i))})"
        print(f"{marker}  {label}")
    raw = input(f"\n  Choice {dim('[' + default + ']')}: ").strip() or default
    try:
        idx = int(raw) - 1
        if 0 <= idx < len(options):
            return options[idx][0]
    except ValueError:
        pass
    return options[int(default) - 1][0]

def multi_choose(prompt: str, options: list[tuple[str, str]], default: str = "1") -> list[str]:
    print(f"\n  {prompt}")
    for i, (_, label) in enumerate(options, 1):
        print(f"  {dim(str(i))})  {label}")
    print(f"  {dim('s')})  Skip for now")
    raw = input(f"\n  Numbers separated by commas {dim('[' + default + ']')}: ").strip() or default
    if raw.lower() == "s":
        return []
    result = []
    for part in raw.split(","):
        try:
            idx = int(part.strip()) - 1
            if 0 <= idx < len(options):
                result.append(options[idx][0])
        except ValueError:
            pass
    return result


# ── System helpers ────────────────────────────────────────────────────────────

def os_name() -> str:
    s = platform.system()
    return {"Darwin": "macos", "Linux": "linux", "Windows": "windows"}.get(s, "unknown")

def which(cmd: str) -> bool:
    return shutil.which(cmd) is not None

def run(cmd: list[str], cwd: str | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, capture_output=True, text=True, cwd=cwd)

def run_visible(cmd: list[str], cwd: str | None = None) -> int:
    """Run command with output visible to user."""
    return subprocess.run(cmd, cwd=cwd).returncode


# ── Prerequisite auto-install ─────────────────────────────────────────────────

_OS = os_name()

_INSTALL_CMDS: dict[str, dict[str, str]] = {
    "go": {
        "macos":  "brew install go",
        "linux":  "sudo apt-get install -y golang-go",
    },
    "bun": {
        "macos":  "curl -fsSL https://bun.sh/install | bash",
        "linux":  "curl -fsSL https://bun.sh/install | bash",
    },
    "docker": {
        "macos":  "brew install --cask docker",
        "linux":  "sudo apt-get install -y docker.io && sudo usermod -aG docker $USER",
    },
    "supabase": {
        "macos":  "brew install supabase/tap/supabase",
        "linux":  "npx supabase --version || npm install -g supabase",
    },
    "redis-cli": {
        "macos":  "brew install redis",
        "linux":  "sudo apt-get install -y redis-tools redis-server",
    },
}

def _offer_install(tool: str, check_cmd: list[str]) -> bool:
    cmd = _INSTALL_CMDS.get(tool, {}).get(_OS)
    if not cmd:
        warn(f"{tool} not found. Please install it manually.")
        return False
    print()
    warn(f"{tool} is not installed.")
    hint(f"Install command: {cmd}")
    if confirm("Run this install command now?", default=True):
        rc = run_visible(cmd.split())
        if rc == 0:
            # Re-check
            r = subprocess.run(check_cmd, capture_output=True, text=True)
            if r.returncode == 0:
                ok(f"{tool} installed successfully.")
                return True
            # Bun needs shell reload — PATH may not reflect yet
            if tool == "bun":
                os.environ["PATH"] = os.environ["PATH"] + f":{Path.home()}/.bun/bin"
                if which("bun"):
                    ok("bun installed (PATH updated for this session).")
                    return True
        fail(f"Install failed. Please install {tool} manually, then re-run: make dev-setup")
        return False
    else:
        fail(f"Please install {tool} manually, then re-run: make dev-setup")
        return False


def check_prerequisites(needs_docker: bool) -> bool:
    header("Checking Prerequisites")

    all_ok = True

    # Python (we're already running — just check version)
    v = sys.version_info
    if v >= (3, 11):
        ok(f"Python {v.major}.{v.minor}.{v.micro}")
    else:
        fail(f"Python 3.11+ required  (you have {v.major}.{v.minor})")
        hint("Install: https://python.org/downloads or use pyenv")
        all_ok = False

    # Go
    if which("go"):
        r = run(["go", "version"])
        ok(r.stdout.strip())
    elif not _offer_install("go", ["go", "version"]):
        all_ok = False

    # Bun or Node
    if which("bun"):
        r = run(["bun", "--version"])
        ok(f"bun {r.stdout.strip()}")
    elif which("node"):
        r = run(["node", "--version"])
        ok(f"node {r.stdout.strip()}")
    elif not _offer_install("bun", ["bun", "--version"]):
        all_ok = False

    # Docker
    if needs_docker:
        if which("docker"):
            r = run(["docker", "--version"])
            ok(r.stdout.strip())
            # Check daemon
            ping = subprocess.run(["docker", "info"], capture_output=True)
            if ping.returncode != 0:
                warn("Docker is installed but not running.")
                hint("Start Docker Desktop, then re-run: make dev-setup")
                all_ok = False
        elif not _offer_install("docker", ["docker", "--version"]):
            all_ok = False

    # Supabase CLI
    if which("supabase"):
        r = run(["supabase", "--version"])
        ok(f"supabase CLI {r.stdout.strip()}")
    elif not _offer_install("supabase", ["supabase", "--version"]):
        all_ok = False

    if not all_ok:
        print()
        fail("Some prerequisites are missing. Fix them and re-run: make dev-setup")
    return all_ok


# ── Terms of Service ──────────────────────────────────────────────────────────

def accept_terms() -> datetime:
    header("Terms of Service  (v{})".format(TERMS_VERSION))
    print(f"""
  By installing and using BugPilot you agree that:

    1. BugPilot accesses your monitoring data only with credentials
       you explicitly provide. No credentials are shared externally.

    2. Data collected during investigations is stored in your own
       infrastructure. BugPilot does not send your data to third parties.

    3. You will not use BugPilot to investigate systems you are not
       authorised to access.

    4. Investigation results (commits, PRs, error logs) are used only
       to help you diagnose incidents in your own systems.

  Full terms: {cyan(TERMS_URL)}
""")
    if not confirm("Do you accept the Terms of Service?", default=False):
        print()
        fail("Terms not accepted. Setup cancelled.")
        sys.exit(1)
    ts = datetime.now(timezone.utc)
    ok(f"Accepted on {ts.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    return ts


# ── 1 / 6  Supabase ───────────────────────────────────────────────────────────

def setup_supabase(env: dict) -> None:
    header("1 / 6  —  Database  (Supabase)")
    print("""
  Supabase stores all BugPilot data: investigations, connector configs,
  org settings, and audit logs. It provides both PostgreSQL and a REST API.
""")

    mode = choose(
        "Where will Supabase run?",
        [
            ("local",  "Local  — Docker container on this machine         (recommended for dev)"),
            ("hosted", "Hosted — your project at supabase.com             (recommended for prod)"),
        ],
    )

    if mode == "local":
        print()
        info("Starting local Supabase stack (Docker required)...")
        info("First run downloads ~1 GB of Docker images — this may take a few minutes.")
        print()

        # supabase start
        rc = run_visible(["supabase", "start"], cwd=str(ROOT / "backend"))
        if rc not in (0, 1):   # 1 = already running
            fail("supabase start failed. Ensure Docker is running and try again.")
            sys.exit(1)

        # Parse supabase status
        r = run(["supabase", "status"], cwd=str(ROOT / "backend"), check=False)
        vals: dict[str, str] = {}
        for line in r.stdout.splitlines():
            if "API URL" in line:
                vals["url"] = line.split(":", 1)[1].strip()
            elif "service_role key" in line:
                vals["service_key"] = line.split(":", 1)[1].strip()
            elif "anon key" in line:
                vals["anon_key"] = line.split(":", 1)[1].strip()
            elif "DB URL" in line:
                vals["db_url"] = line.split(":", 1)[1].strip()

        url         = vals.get("url", "http://localhost:54321")
        service_key = vals.get("service_key", "")
        anon_key    = vals.get("anon_key", "")
        db_url      = vals.get("db_url", "postgresql://postgres:postgres@localhost:54322/postgres")

        print()
        ok(f"SUPABASE_URL         → {url}")
        ok(f"SUPABASE_SERVICE_KEY → {service_key[:24]}...  (auto-filled)")
        ok(f"SUPABASE_ANON_KEY    → {anon_key[:24]}...  (auto-filled)")
        ok(f"DATABASE_URL         → {db_url}")

        env.update({
            "SUPABASE_URL": url,
            "SUPABASE_SERVICE_KEY": service_key,
            "SUPABASE_ANON_KEY": anon_key,
            "VITE_SUPABASE_URL": url,
            "VITE_SUPABASE_PUBLISHABLE_KEY": anon_key,
            "DATABASE_URL": db_url,
        })

    else:
        print(f"""
  {bold("Step 1 — Find your Project URL")}
    supabase.com → log in → select your project
    → Project Settings  (gear icon, left sidebar)
    → API  →  Project URL
    Looks like: {dim("https://abcdefghijkl.supabase.co")}
""")
        url = ask("Project URL")

        print(f"""
  {bold("Step 2 — Service role key")}  {yellow("(keep secret — grants full DB access)")}
    Same page: Project Settings → API
    → Project API keys → {bold("service_role")}  →  Reveal  →  Copy
    Looks like: {dim("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")}
""")
        service_key = ask("service_role key", secret=True)

        print(f"""
  {bold("Step 3 — Anon / public key")}  (safe to expose in the browser)
    Same page: Project Settings → API
    → Project API keys → {bold("anon public")}  →  Copy
    Looks like: {dim("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")}
""")
        anon_key = ask("anon public key", secret=True)

        print(f"""
  {bold("Step 4 — Database connection string")}
    Project Settings → Database → {bold("Connection string")} tab → URI
    Replace {dim("[YOUR-PASSWORD]")} with your database password.
    Looks like: {dim("postgresql://postgres:[password]@db.[ref].supabase.co:5432/postgres")}
""")
        db_url = ask("Database URL (postgresql://...)", secret=True)

        env.update({
            "SUPABASE_URL": url,
            "SUPABASE_SERVICE_KEY": service_key,
            "SUPABASE_ANON_KEY": anon_key,
            "VITE_SUPABASE_URL": url,
            "VITE_SUPABASE_PUBLISHABLE_KEY": anon_key,
            "DATABASE_URL": db_url,
        })


# ── 2 / 6  Redis ──────────────────────────────────────────────────────────────

def setup_redis(env: dict) -> None:
    header("2 / 6  —  Redis  (rate limiting & caching)")
    print("""
  Redis handles rate limiting, caches investigation state between steps,
  and acts as a fallback job queue when AWS SQS is not configured.
""")

    mode = choose(
        "Where will Redis run?",
        [
            ("local",   "Local       — install & run on this machine        (easiest for dev)"),
            ("cloud",   "Redis Cloud — managed Redis at redis.io             (free tier available)"),
            ("upstash", "Upstash     — serverless Redis, billed per request  (free tier, no Docker)"),
            ("custom",  "Custom      — I already have a Redis URL"),
        ],
    )

    if mode == "local":
        redis_url = "redis://localhost:6379/0"
        if which("redis-cli"):
            # Test if already running
            r = subprocess.run(["redis-cli", "ping"], capture_output=True, text=True)
            if r.stdout.strip() == "PONG":
                ok("Redis is already running.")
            else:
                info("Starting Redis...")
                if _OS == "macos":
                    run_visible(["brew", "services", "start", "redis"])
                else:
                    run_visible(["sudo", "systemctl", "start", "redis-server"])
                ok("Redis started.")
        else:
            # Install + start
            print()
            if _OS == "macos":
                install_cmds = [["brew", "install", "redis"], ["brew", "services", "start", "redis"]]
                install_hint = "brew install redis && brew services start redis"
            else:
                install_cmds = [
                    ["sudo", "apt-get", "install", "-y", "redis-server"],
                    ["sudo", "systemctl", "enable", "--now", "redis-server"],
                ]
                install_hint = "sudo apt-get install -y redis-server && sudo systemctl enable --now redis-server"

            warn("Redis is not installed.")
            hint(f"Install command: {install_hint}")
            if confirm("Run this now?", default=True):
                for cmd in install_cmds:
                    run_visible(cmd)
                ok("Redis installed and started.")
            else:
                fail("Please install Redis manually, then re-run: make dev-setup")
                sys.exit(1)
        env["REDIS_URL"] = redis_url

    elif mode == "cloud":
        print(f"""
  {bold("Get a free Redis Cloud database:")}
    1. Go to {cyan("https://redis.io/try-free")}  →  Create free account
    2. Create a new database  →  choose a region close to your server
    3. In the database page  →  {bold("Connect")}  →  copy {bold("Public endpoint")}
    4. Your connection URL format:
       {dim("redis://:{password}@{hostname}:{port}")}
       or with TLS:
       {dim("rediss://:{password}@{hostname}:{port}")}
""")
        env["REDIS_URL"] = ask("Redis Cloud URL", secret=True)

    elif mode == "upstash":
        print(f"""
  {bold("Get a free Upstash Redis database:")}
    1. Go to {cyan("https://upstash.com")}  →  {bold("Create Database")}
    2. Select the region closest to your backend
    3. In the database overview  →  copy {bold("Redis URL")} (starts with rediss://)
""")
        env["REDIS_URL"] = ask("Upstash Redis URL (rediss://...)", secret=True)

    else:
        env["REDIS_URL"] = ask("Redis URL", "redis://localhost:6379/0")

    # Connectivity check
    redis_url = env["REDIS_URL"]
    print()
    info(f"Testing connection to Redis...")
    try:
        parsed = urllib.parse.urlparse(
            redis_url.replace("rediss://", "https://").replace("redis://", "http://")
        )
        host = parsed.hostname or "localhost"
        port = parsed.port or 6379
        s = socket.create_connection((host, port), timeout=4)
        s.close()
        ok(f"Redis reachable at {host}:{port}")
    except Exception as e:
        warn(f"Could not reach Redis ({e})")
        hint("Check the URL is correct. You can edit it in .env and re-run migrations.")


# ── 3 / 6  AWS ────────────────────────────────────────────────────────────────

def setup_aws(env: dict) -> None:
    header("3 / 6  —  AWS  (background worker queues)")
    print("""
  BugPilot's worker processes investigations asynchronously using three
  SQS FIFO queues (critical / standard / retro) and publishes completion
  notifications via SNS.

  This is optional — skip to run investigations inline with no worker.
""")

    mode = choose(
        "How do you want to handle the worker queue?",
        [
            ("skip",       "Skip          — inline mode only, no worker queue  (quickest for dev)"),
            ("aws",        "Real AWS      — I have AWS credentials and SQS/SNS already created"),
            ("localstack", "LocalStack    — run AWS services locally in Docker"),
        ],
        default="1",
    )

    if mode == "skip":
        for k in ("AWS_REGION", "AWS_SQS_P1_URL", "AWS_SQS_P2_URL", "AWS_SQS_RETRO_URL", "AWS_SNS_TOPIC_ARN"):
            env[k] = ""
        info("Worker queue skipped — investigations will run inline.")
        return

    if mode == "localstack":
        if not which("docker"):
            fail("Docker is required for LocalStack.")
            sys.exit(1)
        print()
        info("LocalStack runs SQS and SNS locally on http://localhost:4566")
        if confirm("Start LocalStack container now?", default=True):
            run_visible([
                "docker", "run", "-d", "--rm", "--name", "localstack",
                "-p", "4566:4566",
                "-e", "SERVICES=sqs,sns",
                "localstack/localstack",
            ])
            ok("LocalStack started.")
        hint("You still need to create the queues/topic inside LocalStack.")
        hint("See: https://docs.localstack.cloud/aws/sqs")
        env.update({
            "AWS_REGION": "us-east-1",
            "AWS_SQS_P1_URL":    "http://localhost:4566/000000000000/bugpilot-p1.fifo",
            "AWS_SQS_P2_URL":    "http://localhost:4566/000000000000/bugpilot-p2.fifo",
            "AWS_SQS_RETRO_URL": "http://localhost:4566/000000000000/bugpilot-retro.fifo",
            "AWS_SNS_TOPIC_ARN": "arn:aws:sns:us-east-1:000000000000:bugpilot-investigation-complete",
        })
        return

    # Real AWS
    print(f"""
  {bold("AWS Region")}
    AWS Console → top-right corner → region name dropdown
    Common values: us-east-1, eu-west-1, ap-southeast-2
""")
    region = ask("AWS region", "us-east-1")
    env["AWS_REGION"] = region

    print(f"""
  {bold("SQS Queue URLs")}  — you need 3 FIFO queues (create them first if needed)
    AWS Console → Services → SQS → Queues → click the queue name
    The URL is displayed at the top of the queue detail page.
    Format: {dim(f"https://sqs.{region}.amazonaws.com/{{account-id}}/{{queue-name}}")}

    Create 3 FIFO queues named:
      {dim("bugpilot-p1.fifo")}     — critical priority investigations
      {dim("bugpilot-p2.fifo")}     — standard priority investigations
      {dim("bugpilot-retro.fifo")}  — post-incident retro investigations

    Tip: In the AWS SQS console, tick "FIFO queue" when creating each one.
""")
    env["AWS_SQS_P1_URL"]    = ask("P1 queue URL  (bugpilot-p1.fifo)")
    env["AWS_SQS_P2_URL"]    = ask("P2 queue URL  (bugpilot-p2.fifo)")
    env["AWS_SQS_RETRO_URL"] = ask("Retro queue URL  (bugpilot-retro.fifo)")

    print(f"""
  {bold("SNS Topic ARN")}
    AWS Console → Services → SNS → Topics → click the topic name
    The ARN is displayed at the top of the topic detail page.
    Format: {dim(f"arn:aws:sns:{region}:{{account-id}}:{{topic-name}}")}

    Create one standard SNS topic named: {dim("bugpilot-investigation-complete")}
""")
    env["AWS_SNS_TOPIC_ARN"] = ask("SNS topic ARN")


# ── 4 / 6  LLM ────────────────────────────────────────────────────────────────

def setup_llm(env: dict) -> None:
    header("4 / 6  —  AI Provider")
    print("""
  BugPilot uses a large language model to generate investigation hypotheses
  and plain-English narratives. At least one provider is required.
""")

    mode = choose(
        "Which AI provider do you want to use?",
        [
            ("anthropic", "Anthropic — Claude  (recommended)"),
            ("openai",    "OpenAI    — GPT-4o"),
            ("both",      "Both      — fall back to the other if one is unavailable"),
        ],
    )

    if mode in ("anthropic", "both"):
        print(f"""
  {bold("Anthropic API key")}
    Go to {cyan("https://console.anthropic.com")}  →  API Keys  →  Create Key
    Starts with: {dim("sk-ant-api03-...")}
""")
        env["ANTHROPIC_API_KEY"] = ask("Anthropic API key", secret=True)
    else:
        env["ANTHROPIC_API_KEY"] = ""

    if mode in ("openai", "both"):
        print(f"""
  {bold("OpenAI API key")}
    Go to {cyan("https://platform.openai.com")}  →  API keys  →  Create new secret key
    Starts with: {dim("sk-proj-...")}
""")
        env["OPENAI_API_KEY"] = ask("OpenAI API key", secret=True)
    else:
        env["OPENAI_API_KEY"] = ""


# ── 5 / 6  Security & Slack ───────────────────────────────────────────────────

def setup_security(env: dict) -> None:
    header("5 / 6  —  Security & Integrations")

    # Encryption key
    print(f"  {bold('Connector encryption key')}")
    info("Encrypts connector credentials (API tokens, passwords) stored in the database.")
    info("Auto-generating a secure 32-byte key...")
    try:
        r = run(["openssl", "rand", "-base64", "32"])
        enc_key = r.stdout.strip()
    except Exception:
        import base64, secrets
        enc_key = base64.b64encode(secrets.token_bytes(32)).decode()
    env["CONNECTOR_ENCRYPTION_KEY"] = enc_key
    ok(f"CONNECTOR_ENCRYPTION_KEY generated  ({enc_key[:12]}...)")

    # Slack
    print()
    print(f"  {bold('Slack integration')}  {dim('(optional)')}")
    info("Required only if you want BugPilot to post investigation summaries to Slack.")
    if confirm("Configure Slack now?", default=False):
        print(f"""
  {bold("Slack signing secret")}
    Go to {cyan("https://api.slack.com/apps")}  →  select your app
    →  Basic Information  →  App Credentials  →  {bold("Signing Secret")}  →  Show  →  Copy
""")
        env["SLACK_SIGNING_SECRET"] = ask("Signing secret", secret=True)
    else:
        env["SLACK_SIGNING_SECRET"] = ""
        info("Slack skipped. Set SLACK_SIGNING_SECRET in .env to add it later.")


# ── 6 / 6  App Settings ───────────────────────────────────────────────────────

def setup_app(env: dict) -> None:
    header("6 / 6  —  Application Settings")

    env_mode = choose(
        "Environment mode:",
        [
            ("development", "development — verbose logs, Swagger UI enabled at /docs    (for dev)"),
            ("production",  "production  — structured JSON logs, Swagger UI disabled    (for prod)"),
        ],
    )
    env["BUGPILOT_ENV"] = env_mode

    print()
    info("Backend API URL — where the API server will listen.")
    info("The CLI uses this to connect. Keep the default for local dev.")
    env["BUGPILOT_BASE_URL"] = ask("API base URL", "http://localhost:8000")

    print()
    log_level = ask("Log level  (debug / info / warn / error)", "info")
    env["LOG_LEVEL"] = log_level if log_level in ("debug", "info", "warn", "error") else "info"

    log_format = ask("Log format  (text / json)", "text")
    env["LOG_FORMAT"] = log_format if log_format in ("text", "json") else "text"


# ── Write .env ────────────────────────────────────────────────────────────────

def write_env(env: dict) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        f"# Generated by: make dev-setup  ({now})",
        "# Edit this file to change configuration. Re-run 'make dev-setup' to reconfigure.",
        "",
        "# ── Supabase ────────────────────────────────────────────────────",
        f"SUPABASE_URL={env.get('SUPABASE_URL', '')}",
        f"SUPABASE_SERVICE_KEY={env.get('SUPABASE_SERVICE_KEY', '')}",
        f"SUPABASE_ANON_KEY={env.get('SUPABASE_ANON_KEY', '')}",
        f"DATABASE_URL={env.get('DATABASE_URL', '')}",
        "",
        "# ── Frontend (Vite) — uses the anon key, NOT the service key ─────",
        f"VITE_SUPABASE_URL={env.get('VITE_SUPABASE_URL', '')}",
        f"VITE_SUPABASE_PUBLISHABLE_KEY={env.get('VITE_SUPABASE_PUBLISHABLE_KEY', '')}",
        "",
        "# ── Redis ───────────────────────────────────────────────────────",
        f"REDIS_URL={env.get('REDIS_URL', 'redis://localhost:6379/0')}",
        "",
        "# ── AWS (leave blank if using inline/skip mode) ─────────────────",
        f"AWS_REGION={env.get('AWS_REGION', '')}",
        f"AWS_SQS_P1_URL={env.get('AWS_SQS_P1_URL', '')}",
        f"AWS_SQS_P2_URL={env.get('AWS_SQS_P2_URL', '')}",
        f"AWS_SQS_RETRO_URL={env.get('AWS_SQS_RETRO_URL', '')}",
        f"AWS_SNS_TOPIC_ARN={env.get('AWS_SNS_TOPIC_ARN', '')}",
        "",
        "# ── LLM providers ───────────────────────────────────────────────",
        f"ANTHROPIC_API_KEY={env.get('ANTHROPIC_API_KEY', '')}",
        f"OPENAI_API_KEY={env.get('OPENAI_API_KEY', '')}",
        "",
        "# ── Connector config encryption ─────────────────────────────────",
        "# AES-256 key — do not change after data has been written to the DB",
        f"CONNECTOR_ENCRYPTION_KEY={env.get('CONNECTOR_ENCRYPTION_KEY', '')}",
        "",
        "# ── Slack ───────────────────────────────────────────────────────",
        f"SLACK_SIGNING_SECRET={env.get('SLACK_SIGNING_SECRET', '')}",
        "",
        "# ── Application ─────────────────────────────────────────────────",
        f"BUGPILOT_ENV={env.get('BUGPILOT_ENV', 'development')}",
        f"BUGPILOT_BASE_URL={env.get('BUGPILOT_BASE_URL', 'http://localhost:8000')}",
        f"LOG_LEVEL={env.get('LOG_LEVEL', 'info')}",
        f"LOG_FORMAT={env.get('LOG_FORMAT', 'text')}",
    ]
    ENV_FILE.write_text("\n".join(lines) + "\n")
    ok(f".env written  →  {ENV_FILE}")


# ── Apply: deps + migrations + CLI build ──────────────────────────────────────

def apply_config() -> None:
    # Python dependencies
    info("Installing Python dependencies...")
    rc = run_visible([sys.executable, "-m", "pip", "install", "-q",
                      "-r", str(ROOT / "backend" / "requirements.txt")])
    if rc == 0:
        ok("Python dependencies installed.")
    else:
        warn("pip install had errors. Check output above.")

    # Database migrations
    print()
    info("Running database migrations (supabase db push)...")
    rc = run_visible(["supabase", "db", "push"], cwd=str(ROOT / "backend"))
    if rc == 0:
        ok("Database migrations applied.")
    else:
        warn("Migration step had errors — the DB may already be up to date.")

    # Build CLI
    print()
    info("Building CLI (go build)...")
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    rc = run_visible(
        ["go", "build", "-o", str(dist / "bugpilot"), "./main.go"],
        cwd=str(ROOT / "cli"),
    )
    if rc == 0:
        ok(f"CLI built  →  {dist / 'bugpilot'}")
    else:
        warn("go build failed. Check output above.")

    # Frontend dependencies
    print()
    info("Installing frontend dependencies...")
    pm = "bun" if which("bun") else "npm"
    rc = run_visible([pm, "install"], cwd=str(ROOT / "frontend"))
    if rc == 0:
        ok(f"Frontend dependencies installed ({pm}).")
    else:
        warn("Frontend install had errors. Check output above.")


# ── CLI account setup ─────────────────────────────────────────────────────────

def setup_cli_account(env: dict, terms_ts: datetime) -> None:
    header("CLI Account Setup")

    base_url = env.get("BUGPILOT_BASE_URL", "http://localhost:8000")
    print(f"""
  {bold("BugPilot API key")}
    Open: {cyan(base_url + "/settings/api-keys")}
    → Create a new API key for this developer environment
    Format: {dim("bp_live_...")} or {dim("bp_test_...")}
""")
    api_key = ask("API key", secret=True)
    if not api_key:
        warn("No API key entered. Run 'bugpilot init' later to complete CLI setup.")
        return

    # Validate key via API (also records T&C acceptance)
    print()
    info("Validating key and recording Terms of Service acceptance...")
    payload = json.dumps({
        "terms_accepted": True,
        "terms_version": TERMS_VERSION,
        "terms_accepted_at": terms_ts.isoformat(),
        "cli_version": "dev",
        "platform": platform.system().lower(),
    }).encode()

    org_name = org_id = plan = ""
    try:
        req = urllib.request.Request(
            f"{base_url}/v1/keys/validate",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        org_name = data.get("org_name", "")
        org_id   = data.get("org_id", "")
        plan     = data.get("plan", "")
        ok(f"Connected as {bold(org_name)}  ({plan} plan)")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        warn(f"Key validation returned HTTP {e.code}: {body}")
        hint("Continuing — you can verify with 'bugpilot doctor' once the server is running.")
    except Exception as e:
        warn(f"Could not reach API at {base_url}: {e}")
        hint("This is expected if the backend is not running yet.")
        hint("Your key and config will still be saved.")

    # Default service name
    print()
    info("Default service name — used when you omit --service in commands.")
    info("Examples: payments, auth, api-gateway")
    service = ask("Default service name  (press Enter to skip)")

    # Write ~/.bugpilot/config.yaml (plaintext — 'bugpilot init' encrypts it)
    config_dir = Path.home() / ".bugpilot"
    config_dir.mkdir(mode=0o700, exist_ok=True)
    config_lines = [
        f"api_key: {api_key}",
        f"base_url: {base_url}",
        f"org_id: {org_id}",
        f"org_name: {org_name}",
        f"plan: {plan}",
    ]
    if service:
        config_lines.append(f"default_service: {service}")
    (config_dir / "config.yaml").write_text("\n".join(config_lines) + "\n")
    ok(f"~/.bugpilot/config.yaml written.")
    hint("Note: the API key is stored in plaintext here. Run 'bugpilot init' to encrypt it.")


# ── Connector setup ───────────────────────────────────────────────────────────

def setup_connectors() -> None:
    header("Connect Data Sources")
    print("""
  BugPilot identifies the most likely cause of an incident by correlating
  error data with recent code changes. GitHub is strongly recommended.

  You can add more connectors later with: bugpilot connect <type>
""")

    options = [
        ("github",    "GitHub      — commits, PRs, deployments       (strongly recommended)"),
        ("sentry",    "Sentry      — error tracking & stack traces"),
        ("jira",      "Jira        — link investigations to tickets"),
        ("freshdesk", "Freshdesk   — support ticket context"),
        ("email",     "Email       — IMAP support inbox"),
        ("database",  "Database    — blast radius / error log table"),
        ("log-files", "Log files   — local log files"),
    ]

    chosen = multi_choose(
        "Which data sources do you want to connect now?",
        options,
        default="1",
    )

    if not chosen:
        info("Skipped. Run 'bugpilot connect github' when ready.")
        return

    dist_binary = ROOT / "dist" / "bugpilot"
    if not dist_binary.exists():
        warn("CLI binary not found — skipping connector setup.")
        hint("Run 'make build' then 'bugpilot connect github' to continue.")
        return

    for connector in chosen:
        print()
        run_visible([str(dist_binary), "connect", connector])


# ── Final summary ─────────────────────────────────────────────────────────────

def print_summary(env: dict) -> None:
    base_url = env.get("BUGPILOT_BASE_URL", "http://localhost:8000")
    print()
    print(bold("━" * 58))
    print(bold("  Setup complete"))
    print(bold("━" * 58))
    print(f"""
  {green("✓")}  .env  ({ENV_FILE})
  {green("✓")}  ~/.bugpilot/config.yaml
  {green("✓")}  dist/bugpilot  (CLI binary)

  {bold("Start the stack:")}
    make dev-backend      # API server   →  {base_url}
    make dev-worker       # Background worker
    make dev-frontend     # Dashboard    →  http://localhost:5173

  {bold("Check everything is healthy:")}
    bugpilot doctor

  {bold("Run your first investigation:")}
    bugpilot investigate "payment errors spiking"
""")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    print()
    print(bold("━" * 58))
    print(bold("  BugPilot Developer Setup"))
    print(bold("━" * 58))
    print(f"""
  This wizard will walk you through:

    1. Installing any missing prerequisites
    2. Accepting the Terms of Service
    3. Configuring services  (Supabase, Redis, AWS, AI provider)
    4. Writing .env and installing dependencies
    5. Building the CLI and running database migrations
    6. Setting up your CLI account
    7. Connecting data sources

  Press {bold("Ctrl+C")} at any time to abort.
  Re-run at any time:  {dim("make dev-setup")}
""")
    input(f"  Press {bold('Enter')} to begin...")

    env: dict[str, str] = {}

    # Ask upfront whether local Docker services will be used
    # so we know whether to check for Docker in prerequisites.
    print()
    needs_docker = confirm(
        "Will you run any services locally in Docker?  "
        "(local Supabase, LocalStack)",
        default=True,
    )

    if not check_prerequisites(needs_docker=needs_docker):
        sys.exit(1)

    terms_ts = accept_terms()

    setup_supabase(env)
    setup_redis(env)
    setup_aws(env)
    setup_llm(env)
    setup_security(env)
    setup_app(env)

    header("Writing Configuration & Installing Dependencies")
    write_env(env)
    print()
    apply_config()

    setup_cli_account(env, terms_ts)
    setup_connectors()
    print_summary(env)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        print()
        warn("Setup interrupted.")
        hint("Re-run at any time with: make dev-setup")
        sys.exit(1)
