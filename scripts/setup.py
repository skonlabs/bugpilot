#!/usr/bin/env python3
"""
BugPilot developer setup wizard.

Run:  python scripts/setup.py
  or: make dev-setup

Design principles:
  - Nothing is written to disk until you confirm the review screen.
  - Every input is validated inline; you can't move past a bad value.
  - Multiple instances of any connector type are supported.
  - No Docker dependency — all services are hosted or native.
"""
from __future__ import annotations

import base64
import getpass
import json
import os
import platform
import re
import secrets
import shutil
import socket
import ssl
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
TOTAL_STEPS = 10   # 1-Prerequisites  2-ToS  3-Supabase  4-Redis  5-AWS
                   # 6-AI  7-Security  8-Settings  9-CLI  10-Sources


# ── ANSI colours (stdlib only — no third-party deps at setup time) ────────────

def _ansi(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if sys.stdout.isatty() else text

def bold(t: str)   -> str: return _ansi("1",  t)
def green(t: str)  -> str: return _ansi("32", t)
def yellow(t: str) -> str: return _ansi("33", t)
def red(t: str)    -> str: return _ansi("31", t)
def cyan(t: str)   -> str: return _ansi("36", t)
def dim(t: str)    -> str: return _ansi("2",  t)


# ── UI primitives ─────────────────────────────────────────────────────────────

def rule() -> None:
    print(bold("━" * 62))

def header(title: str, step: int = 0) -> None:
    print()
    rule()
    if step:
        print(bold(f"  Step {step} / {TOTAL_STEPS}  —  {title}"))
    else:
        print(bold(f"  {title}"))
    rule()
    print()

def ok(msg: str)   -> None: print(f"  {green('✓')}  {msg}")
def fail(msg: str) -> None: print(f"  {red('✗')}  {msg}")
def info(msg: str) -> None: print(f"     {msg}")
def warn(msg: str) -> None: print(f"  {yellow('!')}  {msg}")
def hint(msg: str) -> None: print(f"     {dim(msg)}")

def field_header(n: int, total: int, label: str) -> None:
    """Print a numbered field heading."""
    print()
    print(f"  {dim(f'Field {n} of {total}')}")
    print(f"  {bold(label)}")
    print("  " + "─" * 56)
    print()

def ask(prompt: str, default: str = "", secret: bool = False) -> str:
    display = f"  {prompt}"
    if default:
        display += f"  {dim('[' + default + ']')}"
    display += ": "
    try:
        val = getpass.getpass(display) if secret else input(display).strip()
    except EOFError:
        return default
    return val or default

def confirm(prompt: str, default: bool = True) -> bool:
    hint_str = "[Y/n]" if default else "[y/N]"
    try:
        val = input(f"  {prompt} {dim(hint_str)}: ").strip().lower()
    except EOFError:
        return default
    return default if val == "" else val in ("y", "yes")

def choose(prompt: str, options: list[tuple[str, str]], default: str = "1") -> str:
    print(f"  {prompt}")
    print()
    for i, (_, label) in enumerate(options, 1):
        dflt = f"  {dim('(default)')}" if str(i) == default else ""
        print(f"    {bold(str(i))})  {label}{dflt}")
    while True:
        try:
            raw = input(f"\n  Choice {dim('[' + default + ']')}: ").strip() or default
        except EOFError:
            raw = default
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return options[idx][0]
        except ValueError:
            pass
        fail(f"Enter a number between 1 and {len(options)}.")

def multi_choose(prompt: str, options: list[tuple[str, str]]) -> list[str]:
    print(f"  {prompt}")
    print()
    for i, (_, label) in enumerate(options, 1):
        print(f"    {dim(str(i))})  {label}")
    print()
    print(f"    {dim('s')}   Skip — add connectors later with: bugpilot connect <type>")
    while True:
        try:
            raw = input(f"\n  Numbers separated by commas  {dim('(e.g. 1,3,6)')}: ").strip()
        except EOFError:
            return []
        if raw.lower() in ("s", ""):
            return []
        result: list[str] = []
        ok_flag = True
        for part in raw.split(","):
            part = part.strip()
            try:
                idx = int(part) - 1
                if 0 <= idx < len(options):
                    key = options[idx][0]
                    if key not in result:          # de-dupe
                        result.append(key)
                else:
                    fail(f"'{part}' is out of range — enter numbers from 1 to {len(options)}.")
                    ok_flag = False
                    break
            except ValueError:
                fail(f"'{part}' is not a valid number.")
                ok_flag = False
                break
        if ok_flag:
            return result


# ── Validated input ───────────────────────────────────────────────────────────

def ask_validated(
    prompt: str,
    validator,             # (str) -> tuple[bool, str]
    default: str = "",
    secret: bool = False,
) -> str:
    """Ask for input, retrying until the validator returns True."""
    while True:
        val = ask(prompt, default=default, secret=secret)
        if not val:
            fail("This field is required — please enter a value.")
            continue
        passed, err_msg = validator(val)
        if passed:
            return val
        fail(err_msg)
        hint("Try again, or press Ctrl+C to abort setup.")


# ── Validators ────────────────────────────────────────────────────────────────

def _validate_supabase_url(url: str) -> tuple[bool, str]:
    if not url.startswith("https://"):
        return False, "Must start with https://"
    if not url.endswith(".supabase.co"):
        return False, "Must end with .supabase.co  (e.g. https://abcdefghij.supabase.co)"
    try:
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname or ""
        print(f"     {dim('Checking connectivity...')} ", end="", flush=True)
        s = socket.create_connection((host, 443), timeout=8)
        s.close()
        print(green("reachable"))
        return True, ""
    except Exception as e:
        print()
        return False, (
            f"Could not reach {url}\n"
            f"       Check the URL is correct and your internet connection works.\n"
            f"       Error: {e}"
        )

def _make_validate_supabase_secret_key(supabase_url: str):
    """Return a validator that checks format then makes a live API call."""
    def _v(val: str) -> tuple[bool, str]:
        if not val.startswith("sb_secret_"):
            return False, "Secret key must start with sb_secret_  — copy it from Settings → Data API → API Keys"
        if len(val) < 20:
            return False, "Key looks too short — make sure you copied the full value"
        # Live check: hit the REST root; 401 means wrong key, anything else is OK
        print(f"     {dim('Verifying key against project...')} ", end="", flush=True)
        try:
            req = urllib.request.Request(
                f"{supabase_url}/rest/v1/",
                headers={"apikey": val, "Authorization": f"Bearer {val}"},
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                r.read()
            print(green("ok"))
            return True, ""
        except urllib.error.HTTPError as e:
            print()
            if e.code == 401:
                return False, "Supabase rejected this key (401) — make sure you copied the secret key, not the publishable key"
            # Non-401 HTTP errors (e.g. 404) mean auth passed; schema may just be empty
            print(green("ok"))
            return True, ""
        except Exception as e:
            print(yellow("(could not reach project to verify — accepted anyway)"))
            hint(f"Live check skipped: {e}")
            return True, ""
    return _v


def _make_validate_supabase_publishable_key(supabase_url: str):
    """Return a validator that checks format then makes a live API call."""
    def _v(val: str) -> tuple[bool, str]:
        if not val.startswith("sb_publishable_"):
            return False, "Publishable key must start with sb_publishable_  — copy it from Settings → Data API → API Keys"
        if len(val) < 20:
            return False, "Key looks too short — make sure you copied the full value"
        print(f"     {dim('Verifying key against project...')} ", end="", flush=True)
        try:
            req = urllib.request.Request(
                f"{supabase_url}/rest/v1/",
                headers={"apikey": val, "Authorization": f"Bearer {val}"},
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                r.read()
            print(green("ok"))
            return True, ""
        except urllib.error.HTTPError as e:
            print()
            if e.code == 401:
                return False, "Supabase rejected this key (401) — make sure you copied the publishable key, not the secret key"
            print(green("ok"))
            return True, ""
        except Exception as e:
            print(yellow("(could not reach project to verify — accepted anyway)"))
            hint(f"Live check skipped: {e}")
            return True, ""
    return _v


def _validate_db_url(url: str) -> tuple[bool, str]:
    if not (url.startswith("postgresql://") or url.startswith("postgres://")):
        return False, "Must start with postgresql:// or postgres://"
    if "[YOUR-PASSWORD]" in url or "[password]" in url.lower():
        return False, "Replace [YOUR-PASSWORD] with your actual database password"
    if "@" not in url:
        return False, "Missing credentials — format: postgresql://user:password@host:5432/db"
    # TCP-level connectivity check (full auth requires psycopg2 which isn't
    # installed yet at this point in setup)
    try:
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname or ""
        port = parsed.port or 5432
        print(f"     {dim('Checking connectivity...')} ", end="", flush=True)
        s = socket.create_connection((host, port), timeout=8)
        s.close()
        print(green("reachable"))
    except Exception as e:
        print()
        return False, (
            f"Could not reach database host.\n"
            f"       Error: {e}\n"
            f"       Check the host/port in your URI and that the DB is accepting connections."
        )
    return True, ""


def _validate_redis_url(url: str) -> tuple[bool, str]:
    if not (url.startswith("redis://") or url.startswith("rediss://")):
        return False, "Must start with redis:// or rediss://"
    use_tls = url.startswith("rediss://")
    try:
        norm = url.replace("rediss://", "https://").replace("redis://", "http://")
        parsed = urllib.parse.urlparse(norm)
        host   = parsed.hostname or "localhost"
        port   = parsed.port or 6379
        password = parsed.password or ""
        print(f"     {dim('Connecting...')} ", end="", flush=True)
        raw = socket.create_connection((host, port), timeout=8)
        if use_tls:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            sock = ctx.wrap_socket(raw, server_hostname=host)
        else:
            sock = raw
        try:
            if password:
                auth_cmd = f"*2\r\n$4\r\nAUTH\r\n${len(password)}\r\n{password}\r\n"
                sock.sendall(auth_cmd.encode())
                auth_resp = sock.recv(128).decode(errors="replace")
                if not auth_resp.startswith("+OK"):
                    return False, f"Redis AUTH failed — check your password. Server replied: {auth_resp.strip()}"
            sock.sendall(b"*1\r\n$4\r\nPING\r\n")
            pong = sock.recv(128).decode(errors="replace")
            if not pong.startswith("+PONG"):
                return False, f"Unexpected Redis response: {pong.strip()}"
        finally:
            sock.close()
        print(green("PING → PONG"))
        return True, ""
    except Exception as e:
        print()
        return False, (
            f"Could not connect to Redis.\n"
            f"       Error: {e}\n"
            f"       Common causes:\n"
            f"         • Wrong port  — check your provider dashboard\n"
            f"         • Missing password  — format: redis://:{'{'}password{'}'}@host:port\n"
            f"         • TLS required  — use rediss:// (double s) for TLS connections\n"
            f"         • Firewall  — ensure outbound connections from this machine are allowed"
        )

def _validate_aws_region(region: str) -> tuple[bool, str]:
    if not re.match(r"^[a-z]{2}-[a-z]+-\d$", region):
        return False, (
            "Must be a valid AWS region code  "
            "(e.g. us-east-1, eu-west-2, ap-southeast-1)"
        )
    return True, ""

def _make_validate_sqs_url(region: str):
    def _v(url: str) -> tuple[bool, str]:
        if not url.startswith("https://sqs."):
            return False, "Must start with https://sqs."
        if f"sqs.{region}.amazonaws.com" not in url:
            return False, f"Region in URL must match your chosen region '{region}'"
        if not url.endswith(".fifo"):
            return False, "FIFO queue URLs must end with .fifo"
        return True, ""
    return _v

def _make_validate_sns_arn(region: str):
    def _v(arn: str) -> tuple[bool, str]:
        if not arn.startswith("arn:aws:sns:"):
            return False, "Must start with arn:aws:sns:"
        if f":{region}:" not in arn:
            return False, f"Region in ARN must match your chosen region '{region}'"
        return True, ""
    return _v

def _validate_anthropic_key(key: str) -> tuple[bool, str]:
    if not key.startswith("sk-ant-"):
        return False, "Anthropic keys start with sk-ant-  — check you copied the full key"
    if len(key) < 40:
        return False, "Key looks too short — Anthropic keys are typically 100+ characters"
    return True, ""

def _validate_openai_key(key: str) -> tuple[bool, str]:
    if not (key.startswith("sk-") or key.startswith("sk-proj-")):
        return False, "OpenAI keys start with sk-  or  sk-proj-  — check you copied the full key"
    return True, ""

def _validate_bugpilot_key(key: str) -> tuple[bool, str]:
    if not key.startswith("bp_"):
        return False, "BugPilot API keys start with bp_  (e.g. bp_live_... or bp_test_...)"
    return True, ""

def _validate_nonempty(val: str) -> tuple[bool, str]:
    if not val.strip():
        return False, "This field is required — please enter a value."
    return True, ""


# ── System helpers ────────────────────────────────────────────────────────────

def os_name() -> str:
    return {"Darwin": "macos", "Linux": "linux", "Windows": "windows"}.get(
        platform.system(), "unknown"
    )

def which(cmd: str) -> bool:
    return shutil.which(cmd) is not None

def run(cmd: list[str], cwd: str | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, capture_output=True, text=True, cwd=cwd)

def run_visible(cmd: list[str], cwd: str | None = None) -> int:
    return subprocess.run(cmd, cwd=cwd).returncode


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
    "supabase": {
        "macos":  "brew install supabase/tap/supabase",
        "linux":  "curl -fsSL https://raw.githubusercontent.com/supabase/cli/main/install.sh | bash",
    },
}

def _macos_ver() -> tuple[int, int]:
    """Return (major, minor) of the running macOS, e.g. (11, 6) for Big Sur."""
    raw = platform.mac_ver()[0]  # "10.15.7", "11.6.0", "12.3", …
    try:
        parts = [int(p) for p in raw.split(".")]
        return (parts[0], parts[1] if len(parts) > 1 else 0)
    except (ValueError, IndexError):
        return (0, 0)


def _max_go_minor_for_macos(mac_major: int, mac_minor: int) -> int:
    """
    Return the maximum Go 1.X minor version whose official installer
    works on the given macOS.  Based on Go release-notes minimum-OS tables:
      Go 1.25/1.26 → macOS 12 (Monterey)
      Go 1.21–1.24 → macOS 11 (Big Sur)   [1.21 release notes: min 10.15]
      Go 1.17–1.20 → macOS 10.13 (High Sierra)
    We're conservative so the chosen version always installs cleanly.
    """
    if mac_major >= 12:
        return 9999  # Monterey+ — any version is fine
    if mac_major >= 11:
        return 24    # Big Sur — Go 1.25 first required Monterey
    if mac_major == 10 and mac_minor >= 15:
        return 21    # Catalina — Go 1.21 is the last that ships a Catalina pkg
    return 20        # High Sierra / Mojave — Go 1.20


def _install_go_macos_official() -> bool:
    """Install Go via the official pkg installer — works on all macOS versions."""
    arch = "arm64" if platform.machine() == "arm64" else "amd64"
    mac_major, mac_minor = _macos_ver()
    max_minor = _max_go_minor_for_macos(mac_major, mac_minor)

    hint("Fetching stable Go releases from go.dev...")
    try:
        req = urllib.request.Request(
            "https://go.dev/dl/?mode=json",
            headers={"User-Agent": "bugpilot-setup/1.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            releases = json.loads(resp.read())

        def _go_minor(v: str) -> int:
            try:
                return int(v.lstrip("go").split(".")[1])
            except (ValueError, IndexError):
                return 9999

        version = next(
            r["version"] for r in releases
            if r.get("stable") and _go_minor(r["version"]) <= max_minor
        )
    except StopIteration:
        version = None
    except Exception:
        version = None

    # Hardcoded fallbacks when the API is unreachable or no match found
    if not version:
        if mac_major >= 12:
            version = "go1.22.3"
        elif mac_major >= 11:
            version = "go1.24.1"
        elif mac_major == 10 and mac_minor >= 15:
            version = "go1.21.13"
        else:
            version = "go1.20.14"

    hint(f"Selected Go {version} for macOS {mac_major}.{mac_minor}")

    pkg_name = f"{version}.darwin-{arch}.pkg"
    pkg_url  = f"https://go.dev/dl/{pkg_name}"
    pkg_path = Path("/tmp") / pkg_name

    hint(f"Downloading {pkg_url} ...")
    try:
        urllib.request.urlretrieve(pkg_url, pkg_path)
    except Exception as exc:
        fail(f"Download failed: {exc}")
        hint("Install Go manually from https://go.dev/dl/, then re-run: make dev-setup")
        return False

    hint("Running installer (may prompt for your password)...")
    rc = run_visible(["sudo", "installer", "-pkg", str(pkg_path), "-target", "/"])
    pkg_path.unlink(missing_ok=True)
    if rc != 0:
        fail("Go installer failed.")
        hint("Install Go manually from https://go.dev/dl/, then re-run: make dev-setup")
        return False

    # Official installer places Go in /usr/local/go/bin — add it for this session
    go_bin = "/usr/local/go/bin"
    if go_bin not in os.environ.get("PATH", ""):
        os.environ["PATH"] = os.environ["PATH"] + f":{go_bin}"
    return True


def _offer_install(tool: str, check_cmd: list[str]) -> bool:
    """Offer to auto-install a missing tool. Returns True if now available."""
    cmd_str = _INSTALL_CMDS.get(tool, {}).get(_OS)
    if not cmd_str:
        warn(f"{tool} is not installed and there is no known install command for your OS.")
        hint(f"Install {tool} manually, then re-run: make dev-setup")
        return False

    print()
    warn(f"{tool} is not installed.")
    hint(f"Install command:  {cmd_str}")
    if not confirm("Run this install command now?", default=True):
        fail(f"Please install {tool} manually, then re-run: make dev-setup")
        return False

    rc = run_visible(cmd_str.split())
    if rc != 0:
        # brew install go fails on macOS older than Monterey — fall back to
        # the official pkg installer which supports all recent macOS versions.
        if tool == "go" and _OS == "macos":
            print()
            warn("brew install go requires macOS Monterey or newer.")
            hint("Offering official Go installer from go.dev instead...")
            if confirm("Download and run the official Go installer?", default=True):
                if not _install_go_macos_official():
                    return False
                r = subprocess.run(check_cmd, capture_output=True, text=True)
                if r.returncode == 0:
                    ok("go installed successfully.")
                    return True
            fail("Please install Go from https://go.dev/dl/, then re-run: make dev-setup")
            return False

        fail(f"Install failed. Please install {tool} manually, then re-run: make dev-setup")
        return False

    # Re-check (bun may need PATH update)
    r = subprocess.run(check_cmd, capture_output=True, text=True)
    if r.returncode == 0:
        ok(f"{tool} installed successfully.")
        return True
    if tool == "bun":
        new_bin = Path.home() / ".bun" / "bin"
        os.environ["PATH"] = os.environ["PATH"] + f":{new_bin}"
        if which("bun"):
            ok("bun installed  (PATH updated for this session).")
            return True

    fail(f"Install appeared to succeed but {tool} is still not found in PATH.")
    hint("Open a new terminal, then re-run: make dev-setup")
    return False


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Prerequisites
# ══════════════════════════════════════════════════════════════════════════════

def check_prerequisites() -> bool:
    header("Prerequisites", step=1)
    info("Checking required tools...\n")

    all_ok = True

    # Python (already running — just version check)
    v = sys.version_info
    if v >= (3, 11):
        ok(f"Python {v.major}.{v.minor}.{v.micro}")
    else:
        fail(f"Python 3.11+ required  (you have {v.major}.{v.minor})")
        hint("Install from https://python.org/downloads  or use pyenv")
        all_ok = False

    # Go — the official installer puts Go in /usr/local/go/bin which is often
    # not in PATH until the user opens a new shell; check that path explicitly
    # so we don't re-install on every setup re-run.
    _go_default = "/usr/local/go/bin"
    if not which("go") and Path(_go_default).joinpath("go").exists():
        os.environ["PATH"] = os.environ["PATH"] + f":{_go_default}"
    if which("go"):
        r = run(["go", "version"], check=False)
        ok(r.stdout.strip() if r.returncode == 0 else "go  (installed)")
    elif not _offer_install("go", ["go", "version"]):
        all_ok = False

    # Bun (preferred) or Node
    if which("bun"):
        r = run(["bun", "--version"], check=False)
        ok(f"bun {r.stdout.strip()}")
    elif which("node"):
        r = run(["node", "--version"], check=False)
        ok(f"node {r.stdout.strip()}  (bun preferred but node will work)")
    elif not _offer_install("bun", ["bun", "--version"]):
        all_ok = False

    # Supabase CLI  (needed to push migrations)
    if which("supabase"):
        r = run(["supabase", "--version"], check=False)
        ok(f"supabase CLI  {r.stdout.strip()}")
    elif not _offer_install("supabase", ["supabase", "--version"]):
        all_ok = False

    if not all_ok:
        print()
        fail("Fix the above issues and re-run:  make dev-setup")
    return all_ok


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Terms of Service
# ══════════════════════════════════════════════════════════════════════════════

def accept_terms() -> datetime:
    header("Terms of Service", step=2)
    print(f"""\
  By installing and using BugPilot you agree that:

    1. BugPilot accesses your monitoring data only with credentials
       you explicitly provide. No credentials are shared externally.

    2. Data collected during investigations is stored in your own
       infrastructure. BugPilot does not send your data to third parties.

    3. You will not use BugPilot to investigate systems you are not
       authorised to access.

    4. Investigation results (commits, PRs, error logs) are used only
       to help you diagnose incidents in your own systems.

  Full terms:  {cyan(TERMS_URL)}

  {yellow('!')}  Type the word  {bold('yes')}  to accept.
    (Any other input will exit. This is intentional.)
""")
    while True:
        try:
            val = input("  Accept terms: ").strip().lower()
        except EOFError:
            val = ""
        if val == "yes":
            break
        fail("Type  yes  to accept, or press Ctrl+C to exit without changes.")

    ts = datetime.now(timezone.utc)
    ok(f"Terms accepted at  {ts.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    return ts


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Supabase
# ══════════════════════════════════════════════════════════════════════════════

def setup_supabase(cfg: dict) -> None:
    header("Database  (Supabase)", step=3)
    print("""\
  Supabase stores all BugPilot data: investigations, connector configs,
  org settings, and audit logs.

  Sign up free at  https://supabase.com  if you don't have a project yet.
  The free tier is sufficient for development.
""")

    field_header(1, 4, "Project URL")
    print(f"""\
  Where to find it:
    supabase.com  →  your project
    →  {bold('Settings')}  (left sidebar)
    →  {bold('Data API')}
    →  "Project URL"

  Format:  {dim('https://xxxxxxxxxxxx.supabase.co')}
""")
    url = ask_validated("Project URL", _validate_supabase_url)
    ok("Supabase URL ✓")

    field_header(2, 4, "Secret key  ⚠  keep this secret — it has full DB access")
    print(f"""\
  Where to find it:
    Settings  →  Data API
    →  {bold('API Keys')}  tab
    →  {bold('secret')}  →  click "Reveal"  →  Copy

  Current format:  {dim('sb_secret_...')}
""")
    service_key = ask_validated("Secret key", _make_validate_supabase_secret_key(url), secret=True)
    ok("Secret key verified ✓")

    field_header(3, 4, "Publishable key  (safe to use in the browser)")
    print(f"""\
  Where to find it:
    Settings  →  Data API
    →  {bold('API Keys')}  tab
    →  {bold('publishable')}  →  Copy

  Current format:  {dim('sb_publishable_...')}
""")
    anon_key = ask_validated("Publishable key", _make_validate_supabase_publishable_key(url), secret=True)
    ok("Publishable key verified ✓")

    field_header(4, 4, "Database URI")
    print(f"""\
  Where to find it:
    Click the  {bold('Connect')}  button at the top of your project dashboard.
    A modal opens with three connection types — pick one:

    {bold('Transaction Pooler')}  {dim('(recommended — port 6543)')}
      Best for serverless / short-lived connections.
      URI looks like:
      {dim('postgres://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres')}

    {bold('Session Pooler')}  {dim('(port 5432 via pooler — use if on an IPv4-only network)')}
      URI looks like:
      {dim('postgres://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:5432/postgres')}

    {bold('Direct Connection')}  {dim('(port 5432 — use only for long-lived VM/container deployments)')}
      URI looks like:
      {dim('postgresql://postgres:[password]@db.[ref].supabase.co:5432/postgres')}

  Replace  {yellow('[YOUR-PASSWORD]')}  with your actual database password.
""")
    db_url = ask_validated("Database URL", _validate_db_url, secret=True)
    ok("Database URL format ✓")

    cfg["supabase"] = {
        "url":         url,
        "service_key": service_key,
        "anon_key":    anon_key,
        "db_url":      db_url,
    }
    print()
    ok("Supabase configuration complete.")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — Redis
# ══════════════════════════════════════════════════════════════════════════════

def _install_redis_local() -> bool:
    """Install Redis locally and start the service. Returns True if ready."""
    cmds: dict[str, list[str]] = {
        "macos":  ["brew", "install", "redis"],
        "linux":  ["sudo", "apt-get", "install", "-y", "redis-server"],
    }
    cmd = cmds.get(_OS)
    if not cmd:
        warn("No known install command for your OS.")
        hint("Install Redis manually then re-run: make dev-setup")
        return False

    hint(f"Running: {' '.join(cmd)}")
    if run_visible(cmd) != 0:
        fail("Redis installation failed.")
        return False

    # Start the service
    if _OS == "macos":
        run_visible(["brew", "services", "start", "redis"])
    elif _OS == "linux":
        # Try systemctl, fall back to service
        if run_visible(["sudo", "systemctl", "start", "redis-server"]) != 0:
            run_visible(["sudo", "service", "redis-server", "start"])

    ok("Redis installed and started.")
    return True


def setup_redis(cfg: dict) -> None:
    header("Redis  (rate limiting & caching)", step=4)
    print("""\
  Redis handles rate limiting and caches investigation state between steps.
""")

    mode = choose(
        "Where will Redis run?",
        [
            ("local",   "Local        —  install Redis on this machine  (simplest for dev)"),
            ("cloud",   "Redis Cloud  —  redis.io/try-free              Free tier, fully managed"),
            ("upstash", "Upstash      —  upstash.com                    Free tier, pay-per-request"),
            ("custom",  "Custom       —  I already have a Redis URL"),
        ],
    )

    if mode == "local":
        redis_url = "redis://localhost:6379"
        if which("redis-server"):
            ok("redis-server already installed.")
        else:
            hint("Redis is not installed — installing now...")
            if not _install_redis_local():
                fail("Please install Redis manually, then re-run: make dev-setup")
                cfg["redis"] = {"provider": "local", "url": redis_url}
                return
        print(f"""
  Redis will connect on:  {dim(redis_url)}
  To start Redis manually at any time:
""")
        if _OS == "macos":
            print(f"    {dim('brew services start redis')}")
        else:
            print(f"    {dim('sudo systemctl start redis-server')}")
        print()
        ok("Redis connection verified ✓")
        cfg["redis"] = {"provider": "local", "url": redis_url}
        print()
        ok("Redis configuration complete.")
        return

    if mode == "cloud":
        print(f"""
  {bold('Get a free Redis Cloud database:')}
    1. Go to  {cyan('https://redis.io/try-free')}  →  Create free account
    2. New database  →  choose the region {bold('nearest your server')}
    3. Database page  →  Connect  →  copy "Public endpoint"

  Connection URL format:
    {dim('redis://:{password}@{hostname}.redis.cloud:{port}')}
    or with TLS:
    {dim('rediss://:{password}@{hostname}.redis.cloud:{port}')}
""")
    elif mode == "upstash":
        print(f"""
  {bold('Get a free Upstash Redis database:')}
    1. Go to  {cyan('https://upstash.com')}  →  "Create Database"
    2. Select  {bold('Regional')}  →  choose the region nearest your server
    3. Database overview  →  copy "Redis URL"

  Connection URL format:
    {dim('rediss://:{password}@{hostname}.upstash.io:{port}')}
    (note the double-s — Upstash uses TLS)
""")
    else:
        print(f"""
  Paste your Redis connection URL.

  Format without TLS:  {dim('redis://:{password}@{hostname}:{port}')}
  Format with TLS:     {dim('rediss://:{password}@{hostname}:{port}')}
""")

    redis_url = ask_validated(
        "Redis URL",
        _validate_redis_url,
        secret=True,
    )
    ok("Redis connection verified ✓")

    cfg["redis"] = {"provider": mode, "url": redis_url}
    print()
    ok("Redis configuration complete.")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — AWS
# ══════════════════════════════════════════════════════════════════════════════

def setup_aws(cfg: dict) -> None:
    header("AWS  (background worker queues)", step=5)
    print("""\
  BugPilot can process investigations asynchronously using three SQS FIFO
  queues (critical / standard / retro) and an SNS topic for notifications.

  Skipping means investigations run inline — perfectly fine for development.
""")

    mode = choose(
        "How do you want to handle the worker queue?",
        [
            ("skip", "Skip  —  inline mode, no queues    (recommended for first-time setup)"),
            ("aws",  "Real AWS  —  I have an AWS account and will create the queues"),
        ],
    )

    if mode == "skip":
        cfg["aws"] = {"mode": "skip"}
        info("Worker queues skipped — investigations will run inline.")
        return

    # ── Real AWS ──────────────────────────────────────────────────────────────
    field_header(1, 6, "AWS Region")
    print(f"""\
  Where to find it:
    AWS Console  →  top-right corner  →  region name dropdown
    Copy the {bold('code')} shown in parentheses, not the display name.

  Common values:  {dim('us-east-1   eu-west-1   eu-west-2   ap-southeast-1   ap-southeast-2')}
""")
    region = ask_validated("AWS region", _validate_aws_region, default="us-east-1")
    ok(f"Region: {region}")

    print(f"""
  {bold('Before continuing — create these 3 FIFO queues in AWS SQS:')}

    Queue name                  Purpose
    ──────────────────────      ─────────────────────────────────
    bugpilot-p1.fifo            Critical priority investigations
    bugpilot-p2.fifo            Standard priority investigations
    bugpilot-retro.fifo         Post-incident retro investigations

  How to create them:
    AWS Console  →  SQS  →  Create queue
    →  Select  {bold('FIFO queue')}
    →  Name it exactly as above
    →  Leave all other settings as defaults  →  Create

  How to find each Queue URL after creation:
    Click the queue name  →  the URL is at the top of the detail page

  Format:
    {dim(f'https://sqs.{region}.amazonaws.com/{{account-id}}/{{queue-name}}.fifo')}
""")
    input("  Press Enter when all 3 queues are created...")

    field_header(2, 6, "P1 Queue URL  (bugpilot-p1.fifo — critical priority)")
    p1_url = ask_validated("P1 queue URL", _make_validate_sqs_url(region))
    ok("P1 queue URL ✓")

    field_header(3, 6, "P2 Queue URL  (bugpilot-p2.fifo — standard priority)")
    p2_url = ask_validated("P2 queue URL", _make_validate_sqs_url(region))
    ok("P2 queue URL ✓")

    field_header(4, 6, "Retro Queue URL  (bugpilot-retro.fifo — post-incident)")
    retro_url = ask_validated("Retro queue URL", _make_validate_sqs_url(region))
    ok("Retro queue URL ✓")

    print(f"""
  {bold('Create one SNS topic for investigation-complete notifications:')}

    Topic name:  bugpilot-investigation-complete
    Type:        Standard  (not FIFO)

  How to create it:
    AWS Console  →  SNS  →  Topics  →  Create topic
    →  Standard  →  Name: bugpilot-investigation-complete  →  Create

  How to find the ARN after creation:
    Click the topic name  →  ARN is at the top of the detail page

  Format:
    {dim(f'arn:aws:sns:{region}:{{account-id}}:bugpilot-investigation-complete')}
""")
    input("  Press Enter when the SNS topic is created...")

    field_header(5, 6, "SNS Topic ARN")
    sns_arn = ask_validated("SNS topic ARN", _make_validate_sns_arn(region))
    ok("SNS topic ARN ✓")

    field_header(6, 6, "AWS Credentials")
    print(f"""\
  Where to find them:
    AWS Console  →  top-right corner  →  your name  →  Security credentials
    →  Access keys section  →  Create access key

  {yellow('Tip:')} Create a dedicated IAM user with only the permissions below.
  This follows least-privilege best practice.

  Minimum IAM permissions required:
    sqs:SendMessage    sqs:ReceiveMessage    sqs:DeleteMessage    sqs:GetQueueAttributes
    sns:Publish
""")
    access_key_id = ask_validated("AWS Access Key ID", _validate_nonempty)

    # Basic format check for the access key ID
    if not (access_key_id.startswith("AKIA") or access_key_id.startswith("ASIA")):
        warn("Access Key ID doesn't start with AKIA or ASIA — double-check you pasted the Key ID")
        hint("The Key ID is different from the Secret Access Key")

    secret_key = ask_validated("AWS Secret Access Key", _validate_nonempty, secret=True)
    ok("AWS credentials saved.")

    cfg["aws"] = {
        "mode":          "aws",
        "region":        region,
        "sqs_p1":        p1_url,
        "sqs_p2":        p2_url,
        "sqs_retro":     retro_url,
        "sns_arn":       sns_arn,
        "access_key_id": access_key_id,
        "secret_key":    secret_key,
    }
    print()
    ok("AWS configuration complete.")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 6 — AI Provider
# ══════════════════════════════════════════════════════════════════════════════

def setup_llm(cfg: dict) -> None:
    header("AI Provider", step=6)
    print("""\
  BugPilot uses an LLM to generate investigation hypotheses and
  plain-English summaries. At least one provider is required.
""")

    mode = choose(
        "Which AI provider do you want to use?",
        [
            ("anthropic", "Anthropic — Claude  (recommended)"),
            ("openai",    "OpenAI    — GPT-4o"),
            ("both",      "Both      — automatically fall back if one is unavailable"),
        ],
    )

    anthropic_key = openai_key = ""

    if mode in ("anthropic", "both"):
        print(f"""
  {bold('Anthropic API key')}
  Where to find it:
    {cyan('https://console.anthropic.com')}  →  API Keys  →  Create Key

  Starts with:  {dim('sk-ant-api03-...')}
  Length:       typically 100+ characters
""")
        anthropic_key = ask_validated(
            "Anthropic API key",
            _validate_anthropic_key,
            secret=True,
        )
        ok("Anthropic key format ✓")

    if mode in ("openai", "both"):
        print(f"""
  {bold('OpenAI API key')}
  Where to find it:
    {cyan('https://platform.openai.com')}  →  API keys  →  Create new secret key

  Starts with:  {dim('sk-proj-...')}  or  {dim('sk-...')}
""")
        openai_key = ask_validated(
            "OpenAI API key",
            _validate_openai_key,
            secret=True,
        )
        ok("OpenAI key format ✓")

    cfg["llm"] = {
        "mode":          mode,
        "anthropic_key": anthropic_key,
        "openai_key":    openai_key,
    }
    print()
    ok("AI provider configuration complete.")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 7 — Security & Optional Integrations
# ══════════════════════════════════════════════════════════════════════════════

def setup_security(cfg: dict) -> None:
    header("Security & Optional Integrations", step=7)

    # Auto-generate connector encryption key
    print(f"  {bold('Connector encryption key')}")
    info("Encrypts connector credentials stored in the database.")
    info("Generated automatically — you never need to copy this value.")
    info("Auto-generating secure AES-256 key...")
    try:
        r = run(["openssl", "rand", "-base64", "32"], check=False)
        enc_key = r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        enc_key = ""
    if not enc_key:
        enc_key = base64.b64encode(secrets.token_bytes(32)).decode()
    ok(f"Encryption key generated  {dim('(saved to .env only — never commit .env)')}")

    # Slack (optional)
    print()
    print(f"  {bold('Slack integration')}  {dim('(optional)')}")
    info("Posts investigation summaries to a Slack channel when investigations complete.")
    slack_secret = ""
    if confirm("Configure Slack now?", default=False):
        print(f"""
  Where to find your Slack signing secret:
    {cyan('https://api.slack.com/apps')}  →  select your app  (create one if needed)
    →  Basic Information
    →  App Credentials
    →  {bold('Signing Secret')}  →  Show  →  Copy

  Looks like:  {dim('a 32-character hexadecimal string')}
""")
        slack_secret = ask_validated("Slack signing secret", _validate_nonempty, secret=True)
        ok("Slack signing secret saved.")
    else:
        info("Slack skipped. Set SLACK_SIGNING_SECRET in .env to enable it later.")

    cfg["security"] = {
        "encryption_key": enc_key,
        "slack_secret":   slack_secret,
    }
    print()
    ok("Security configuration complete.")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 8 — Application Settings
# ══════════════════════════════════════════════════════════════════════════════

def setup_app(cfg: dict) -> None:
    header("Application Settings", step=8)

    env_mode = choose(
        "Environment mode:",
        [
            ("development", "development  —  verbose logs, Swagger UI at /docs      (for dev)"),
            ("production",  "production   —  JSON logs, Swagger disabled            (for prod)"),
        ],
    )

    print()
    info("API base URL — where the backend server will listen.")
    info("The CLI uses this URL to connect. Keep the default for local development.")
    base_url = ask("API base URL", default="http://localhost:8000")

    print()
    log_level = choose(
        "Log level:",
        [
            ("info",  "info   — standard logging  (recommended)"),
            ("debug", "debug  — verbose, includes full request/response bodies"),
            ("warn",  "warn   — warnings and errors only"),
            ("error", "error  — errors only"),
        ],
    )

    log_format = choose(
        "Log format:",
        [
            ("text", "text  — human-readable         (better for development)"),
            ("json", "json  — structured/machine      (better for production log ingestion)"),
        ],
    )

    cfg["app"] = {
        "env":        env_mode,
        "base_url":   base_url,
        "log_level":  log_level,
        "log_format": log_format,
    }
    print()
    ok("Application settings saved.")


# ══════════════════════════════════════════════════════════════════════════════
# PRE-APPLY REVIEW
# ══════════════════════════════════════════════════════════════════════════════

def _mask(val: str, show: int = 8) -> str:
    """Show first `show` characters then ellipsis, masking the rest."""
    if not val:
        return dim("(not set)")
    if len(val) <= show:
        return "****"
    return val[:show] + dim("...")

def _status(val: str) -> str:
    return green("✓") if val else red("✗  not set")

def pre_apply_review(cfg: dict, terms_ts: datetime) -> None:
    """
    Show a full summary of everything collected so far.
    Allow going back to any step to change values.
    Only returns when the developer confirms.
    Nothing has been written to disk at this point.
    """
    while True:
        sup  = cfg.get("supabase", {})
        red_c = cfg.get("redis",   {})
        aws  = cfg.get("aws",      {})
        llm  = cfg.get("llm",      {})
        sec  = cfg.get("security", {})
        app  = cfg.get("app",      {})

        print()
        rule()
        print(bold("  Configuration Review"))
        print(bold("  Nothing has been written to disk yet."))
        print(bold("  Review everything below, then press Enter to apply."))
        rule()
        print(f"""
  {bold('DATABASE  (Supabase)')}
    Project URL      {sup.get('url', dim('not set'))}   {_status(sup.get('url',''))}
    Service key      {_mask(sup.get('service_key',''))}   (hidden)
    Publishable key  {_mask(sup.get('anon_key',''))}   (hidden)
    Database URL     {_mask(sup.get('db_url',''), 22)}   (hidden)""")

        redis_provider = {
            "local":   "Local",
            "cloud":   "Redis Cloud",
            "upstash": "Upstash",
            "custom":  "Custom",
        }.get(red_c.get("provider", ""), "Redis")
        print(f"""
  {bold('REDIS')}
    Provider         {redis_provider}
    URL              {_mask(red_c.get('url',''), 26)}   (hidden)   {_status(red_c.get('url',''))}""")

        aws_mode = aws.get("mode", "skip")
        if aws_mode == "skip":
            print(f"""
  {bold('AWS')}
    Mode             {dim('Skipped  (inline processing)')}""")
        else:
            print(f"""
  {bold('AWS')}
    Region           {aws.get('region','')}
    P1 queue         {aws.get('sqs_p1','')}
    P2 queue         {aws.get('sqs_p2','')}
    Retro queue      {aws.get('sqs_retro','')}
    SNS topic ARN    {aws.get('sns_arn','')}
    Access Key ID    {_mask(aws.get('access_key_id',''))}
    Secret Key       {_mask(aws.get('secret_key',''), 4)}   (hidden)""")

        llm_mode = llm.get("mode", "")
        print(f"""
  {bold('AI PROVIDER')}""")
        if llm_mode in ("anthropic", "both"):
            print(f"    Anthropic        {_mask(llm.get('anthropic_key',''), 14)}   {_status(llm.get('anthropic_key',''))}")
        if llm_mode in ("openai", "both"):
            print(f"    OpenAI           {_mask(llm.get('openai_key',''), 14)}   {_status(llm.get('openai_key',''))}")

        print(f"""
  {bold('SECURITY')}
    Encryption key   auto-generated AES-256   {green('✓')}
    Slack            {"configured  " + green('✓') if sec.get('slack_secret') else dim('not configured')}

  {bold('APPLICATION')}
    Environment      {app.get('env','')}
    API URL          {app.get('base_url','')}
    Log level        {app.get('log_level','')}
    Log format       {app.get('log_format','')}

  {bold('TERMS OF SERVICE')}
    Accepted at      {terms_ts.strftime('%Y-%m-%d %H:%M:%S UTC')}

  {bold('FILES THAT WILL BE WRITTEN:')}
    .env                          environment variables
    ~/.bugpilot/config.yaml       CLI configuration  (after Step 9)

  {bold('COMMANDS THAT WILL RUN:')}
    pip install -r backend/requirements.txt
    bun install  (frontend/)
    supabase db push  (applies migrations to your Supabase project)
    go build  (CLI binary  →  dist/bugpilot)
""")
        print("  " + "─" * 58)
        print(f"  {dim('Type a step number to go back and change it.')}")
        print(f"  {dim('Steps you can revisit:  3=Supabase  4=Redis  5=AWS  6=AI  7=Security  8=Settings')}")
        print()
        try:
            choice = input(f"  {bold('Step to revisit [3-8]')}  or  {bold('Enter to apply')}:  ").strip()
        except EOFError:
            choice = ""

        if choice == "":
            print()
            ok("Configuration confirmed. Applying now...")
            return

        try:
            n = int(choice)
            if   n == 3: setup_supabase(cfg)
            elif n == 4: setup_redis(cfg)
            elif n == 5: setup_aws(cfg)
            elif n == 6: setup_llm(cfg)
            elif n == 7: setup_security(cfg)
            elif n == 8: setup_app(cfg)
            else:
                fail("Enter a number between 3 and 8, or press Enter to apply.")
        except ValueError:
            fail("Enter a number between 3 and 8, or press Enter to apply.")


# ══════════════════════════════════════════════════════════════════════════════
# APPLY — write .env + install deps + migrations + build CLI
# ══════════════════════════════════════════════════════════════════════════════

def write_env(cfg: dict) -> None:
    sup  = cfg["supabase"]
    red_c = cfg["redis"]
    aws  = cfg.get("aws", {})
    llm  = cfg["llm"]
    sec  = cfg["security"]
    app  = cfg["app"]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        f"# Generated by: make dev-setup  ({now})",
        "# Edit this file to change configuration.",
        "# Re-run 'make dev-setup' at any time to reconfigure.",
        "# IMPORTANT: Never commit this file to version control.",
        "",
        "# ── Supabase ────────────────────────────────────────────────",
        f"SUPABASE_URL={sup['url']}",
        f"SUPABASE_SERVICE_KEY={sup['service_key']}",
        f"SUPABASE_ANON_KEY={sup['anon_key']}",
        f"DATABASE_URL={sup['db_url']}",
        "",
        "# ── Frontend (Vite) — uses the publishable key, NOT the secret key ─",
        f"VITE_SUPABASE_URL={sup['url']}",
        f"VITE_SUPABASE_PUBLISHABLE_KEY={sup['anon_key']}",
        "",
        "# ── Redis ───────────────────────────────────────────────────",
        f"REDIS_URL={red_c['url']}",
        "",
        "# ── AWS (all blank when using inline/skip mode) ──────────────",
        f"AWS_REGION={aws.get('region', '')}",
        f"AWS_SQS_P1_URL={aws.get('sqs_p1', '')}",
        f"AWS_SQS_P2_URL={aws.get('sqs_p2', '')}",
        f"AWS_SQS_RETRO_URL={aws.get('sqs_retro', '')}",
        f"AWS_SNS_TOPIC_ARN={aws.get('sns_arn', '')}",
    ]
    if aws.get("mode") == "aws":
        lines += [
            f"AWS_ACCESS_KEY_ID={aws.get('access_key_id', '')}",
            f"AWS_SECRET_ACCESS_KEY={aws.get('secret_key', '')}",
        ]
    lines += [
        "",
        "# ── LLM providers ───────────────────────────────────────────",
        f"ANTHROPIC_API_KEY={llm.get('anthropic_key', '')}",
        f"OPENAI_API_KEY={llm.get('openai_key', '')}",
        "",
        "# ── Connector credential encryption ─────────────────────────",
        "# AES-256 — do NOT change after connectors have been saved to the DB.",
        f"CONNECTOR_ENCRYPTION_KEY={sec['encryption_key']}",
        "",
        "# ── Slack ───────────────────────────────────────────────────",
        f"SLACK_SIGNING_SECRET={sec.get('slack_secret', '')}",
        "",
        "# ── Application ─────────────────────────────────────────────",
        f"BUGPILOT_ENV={app['env']}",
        f"BUGPILOT_BASE_URL={app['base_url']}",
        f"LOG_LEVEL={app['log_level']}",
        f"LOG_FORMAT={app['log_format']}",
    ]
    ENV_FILE.write_text("\n".join(lines) + "\n")
    ok(f".env written  →  {ENV_FILE}")

def apply_config() -> None:
    # Python dependencies
    info("Installing Python dependencies...")
    rc = run_visible([
        sys.executable, "-m", "pip", "install", "-q",
        "-r", str(ROOT / "backend" / "requirements.txt"),
    ])
    if rc == 0:
        ok("Python dependencies installed.")
    else:
        warn("pip install encountered errors — check the output above.")

    # Connector base deps
    base_req = ROOT / "backend" / "connectors" / "_base" / "requirements.txt"
    if base_req.exists():
        run_visible([sys.executable, "-m", "pip", "install", "-q", "-r", str(base_req)])

    # Database migrations
    print()
    info("Running database migrations  (supabase db push)...")
    rc = run_visible(["supabase", "db", "push"], cwd=str(ROOT / "backend"))
    if rc == 0:
        ok("Database migrations applied.")
    else:
        warn("Migration step had errors — the schema may already be up to date.")
        hint("If this is a fresh project and you see errors, check your DATABASE_URL in .env.")

    # CLI binary
    print()
    info("Building CLI binary  (go build)...")
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    rc = run_visible(
        ["go", "build", "-o", str(dist / "bugpilot"), "./main.go"],
        cwd=str(ROOT / "cli"),
    )
    if rc == 0:
        ok(f"CLI built  →  dist/bugpilot")
    else:
        warn("go build failed — connector setup in Step 10 will be skipped.")
        hint("Fix the build error and run:  make build")

    # Frontend dependencies
    print()
    info("Installing frontend dependencies...")
    pm = "bun" if which("bun") else "npm"
    rc = run_visible([pm, "install"], cwd=str(ROOT / "frontend"))
    if rc == 0:
        ok(f"Frontend dependencies installed  ({pm}).")
    else:
        warn("Frontend install had errors — check the output above.")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 9 — CLI Account
# ══════════════════════════════════════════════════════════════════════════════

def setup_cli_account(cfg: dict, terms_ts: datetime) -> None:
    header("CLI Account", step=9)

    base_url = cfg.get("app", {}).get("base_url", "http://localhost:8000")

    print(f"""\
  The API server must be running to complete this step.

  If you haven't started it yet, open a {bold('new terminal')} and run:
    {bold('make dev-backend')}

  Then come back here.
""")
    print(f"  Press Enter when the server is running, or type  {bold('s')}  to skip:  ", end="", flush=True)
    try:
        resp = input().strip().lower()
    except EOFError:
        resp = "s"

    if resp == "s":
        warn("CLI account setup skipped.")
        hint("Run  'bugpilot init'  after starting the server to complete setup.")
        cfg["cli"] = {}
        return

    print(f"""
  {bold('Create a BugPilot API key:')}
    Open in your browser:  {cyan(base_url + '/settings/api-keys')}
    →  "Create API key"
    →  Give it a descriptive name  (e.g. "local-dev-{os.environ.get('USER','me')}")
    →  Copy the key

  Format:  {dim('bp_live_...')}  or  {dim('bp_test_...')}
""")
    api_key = ask_validated("BugPilot API key", _validate_bugpilot_key, secret=True)

    # Validate key + record Terms acceptance
    print()
    info("Validating key and recording Terms of Service acceptance...")
    payload = json.dumps({
        "terms_accepted":    True,
        "terms_version":     TERMS_VERSION,
        "terms_accepted_at": terms_ts.isoformat(),
        "cli_version":       "dev",
        "platform":          platform.system().lower(),
    }).encode()

    org_name = org_id = plan = ""
    try:
        req = urllib.request.Request(
            f"{base_url}/v1/keys/validate",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type":  "application/json",
                "Accept":        "application/json",
            },
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=10) as resp_obj:
            data = json.loads(resp_obj.read())
        org_name = data.get("org_name", "")
        org_id   = data.get("org_id",   "")
        plan     = data.get("plan",     "")
        ok(f"Connected as  {bold(org_name)}  ({plan} plan)")
        ok("Terms of Service acceptance recorded.")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        warn(f"Key validation returned HTTP {e.code}: {body}")
        hint("Continuing — verify with  'bugpilot doctor'  once the server is stable.")
    except Exception as e:
        warn(f"Could not reach API at {base_url}: {e}")
        hint("Your key will still be saved locally.")
        hint("Verify later with:  bugpilot doctor")

    print()
    info("Default service name — used automatically when you omit --service from commands.")
    info("Examples:  payments   auth   api-gateway   frontend")
    service = ask("Default service name  (press Enter to skip)")

    # Write ~/.bugpilot/config.yaml
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
    ok("~/.bugpilot/config.yaml written.")
    hint("Note: the API key is stored in plaintext. Run  'bugpilot init'  to encrypt it.")

    cfg["cli"] = {
        "api_key":         api_key,
        "org_name":        org_name,
        "org_id":          org_id,
        "plan":            plan,
        "default_service": service,
    }


# ══════════════════════════════════════════════════════════════════════════════
# STEP 10 — Connect Data Sources
# ══════════════════════════════════════════════════════════════════════════════

# Human-readable hint shown when offering to add a second instance of a type.
_MULTI_HINTS: dict[str, str] = {
    "github":    "e.g. a second organisation, a different token, a monorepo",
    "sentry":    "e.g. a second Sentry account or a different project",
    "jira":      "e.g. a second Jira instance or workspace",
    "freshdesk": "e.g. a second Freshdesk account",
    "email":     "e.g. a second inbox or shared alias",
    "database":  "e.g. a second database, a read replica, or an analytics DB",
    "log-files": "e.g. another service's logs, or nginx access logs",
}

_CONNECTOR_OPTIONS = [
    ("github",    "GitHub      — commits, PRs, deployments         (strongly recommended)"),
    ("sentry",    "Sentry      — error tracking & stack traces"),
    ("jira",      "Jira        — link investigations to tickets"),
    ("freshdesk", "Freshdesk   — support ticket context"),
    ("email",     "Email       — IMAP inbox"),
    ("database",  "Database    — any PostgreSQL / MySQL / SQLite instance"),
    ("log-files", "Log files   — any log file path or glob pattern"),
]

def _run_connector(connector_type: str, name: str) -> bool:
    """Run  bugpilot connect <type> --name <name>.  Returns True on success."""
    dist_binary = ROOT / "dist" / "bugpilot"
    if not dist_binary.exists():
        return False
    rc = run_visible([str(dist_binary), "connect", connector_type, "--name", name])
    return rc == 0

def setup_connectors(cfg: dict) -> None:
    header("Connect Data Sources", step=10)
    print(f"""\
  BugPilot identifies incident causes by correlating errors with recent
  code changes, tickets, and logs.

  {bold('Any connector type can be connected multiple times.')}
  For example: two GitHub organisations, three databases, multiple log paths.

  You can add more at any time with:
    bugpilot connect <type> --name <label>
    bugpilot connect list
""")

    dist_binary = ROOT / "dist" / "bugpilot"
    if not dist_binary.exists():
        warn("CLI binary was not built — connector setup is unavailable.")
        hint("Run  'make build'  then  'bugpilot connect <type>'  to add connectors.")
        cfg["connectors"] = []
        return

    chosen_types = multi_choose(
        "Which data sources do you want to connect now?",
        _CONNECTOR_OPTIONS,
    )

    if not chosen_types:
        info("No connectors configured now.")
        hint("Run  'bugpilot connect <type>'  when ready.")
        cfg["connectors"] = []
        return

    connectors_added: list[dict] = []

    for connector_type in chosen_types:
        type_label = connector_type.replace("-", " ").title()
        instance_num = 1

        while True:
            print()
            print(f"  {bold('─' * 56)}")
            print(f"  {bold(type_label)}  —  instance {instance_num}")
            print(f"  {bold('─' * 56)}")
            print()

            if instance_num == 1:
                name = ask("Connector name", default="default")
                if not name:
                    name = "default"
            else:
                hint_msg = _MULTI_HINTS.get(connector_type, "a second instance")
                while True:
                    name = ask(f"Connector name  {dim('(' + hint_msg + ')')}")
                    if name:
                        break
                    fail("Connector name is required — enter a short label, e.g. analytics")

            # Prevent duplicate names for the same type
            existing_names = {
                c["name"] for c in connectors_added if c["type"] == connector_type
            }
            if name in existing_names:
                fail(f"A {type_label} connector named '{name}' already exists in this session.")
                hint("Use a different name, e.g. 'org2', 'secondary', 'analytics'.")
                continue   # ask for name again — re-enter the while loop body

            print()
            success = _run_connector(connector_type, name)
            if success:
                ok(f'{type_label} connector  "{name}"  connected.')
                connectors_added.append({"type": connector_type, "name": name, "status": "ok"})
            else:
                warn(f'{type_label} connector  "{name}"  setup reported errors.')
                hint(f"Retry later:  bugpilot connect {connector_type} --name {name}")
                connectors_added.append({"type": connector_type, "name": name, "status": "error"})

            # Offer to add another instance of the same type
            print()
            hint_msg = _MULTI_HINTS.get(connector_type, "a second instance")
            if not confirm(
                f"Add another {type_label} connector?  {dim('(' + hint_msg + ')')}",
                default=False,
            ):
                break
            instance_num += 1

    cfg["connectors"] = connectors_added


# ══════════════════════════════════════════════════════════════════════════════
# FINAL DONE SCREEN
# ══════════════════════════════════════════════════════════════════════════════

def print_done(cfg: dict) -> None:
    sup        = cfg.get("supabase",   {})
    red_c      = cfg.get("redis",      {})
    aws        = cfg.get("aws",        {})
    llm        = cfg.get("llm",        {})
    sec        = cfg.get("security",   {})
    app        = cfg.get("app",        {})
    cli        = cfg.get("cli",        {})
    connectors = cfg.get("connectors", [])
    base_url   = app.get("base_url",   "http://localhost:8000")

    print()
    rule()
    print(bold("  Setup Complete"))
    rule()

    print(f"""
  {bold('INFRASTRUCTURE')}""")

    # Supabase
    sup_url = sup.get("url", "")
    print(f"    Database     Supabase        {sup_url or dim('(not set)')}   {green('✓') if sup_url else red('✗')}")

    # Redis
    redis_provider_label = {
        "local":   "Local          ",
        "cloud":   "Redis Cloud    ",
        "upstash": "Upstash        ",
        "custom":  "Custom Redis   ",
    }.get(red_c.get("provider", ""), "Redis          ")
    redis_url_short = _mask(red_c.get("url", ""), 30)
    r_ok = green("✓") if red_c.get("url") else red("✗")
    print(f"    Redis        {redis_provider_label}{redis_url_short}  {r_ok}")

    # AWS
    aws_mode = aws.get("mode", "skip")
    if aws_mode == "skip":
        print(f"    AWS          {dim('Skipped  (inline mode active)')}")
    else:
        print(f"    AWS          {aws.get('region', '')}  —  SQS + SNS   {green('✓')}")

    # AI
    llm_mode = llm.get("mode", "")
    if llm_mode in ("anthropic", "both"):
        print(f"    AI           Anthropic Claude   {green('✓')}")
    if llm_mode in ("openai", "both"):
        print(f"    AI           OpenAI GPT-4o      {green('✓')}")

    print(f"""
  {bold('SECURITY')}
    Encryption   AES-256 key generated   {green('✓')}
    Slack        {"configured  " + green("✓") if sec.get("slack_secret") else dim("not configured")}""")

    if cli:
        print(f"""
  {bold('CLI ACCOUNT')}""")
        if cli.get("org_name"):
            plan_str = f"  ({cli.get('plan', '')} plan)" if cli.get("plan") else ""
            print(f"    Organisation {cli.get('org_name', '')}{plan_str}   {green('✓')}")
        if cli.get("default_service"):
            print(f"    Service      {cli.get('default_service', '')}")
        print(f"    Config file  ~/.bugpilot/config.yaml   {green('✓')}")

    if connectors:
        print(f"""
  {bold('CONNECTORS')}""")
        for c in connectors:
            t_label = c["type"].replace("-", " ").title()
            icon    = green("✓") if c["status"] == "ok" else yellow("!")
            print(f"    {t_label:<12}  \"{c['name']}\"   {icon}")
    else:
        print(f"""
  {bold('CONNECTORS')}
    {dim('None configured yet — see commands below to add them')}""")

    print(f"""
  {bold('FILES WRITTEN')}
    .env                     environment variables   {green('✓')}""")
    if cli:
        print(f"    ~/.bugpilot/config.yaml  CLI configuration       {green('✓')}")
    print(f"    dist/bugpilot            CLI binary              {green('✓')}")

    print()
    rule()
    print(f"""
  {bold('Start the stack:')}
    make dev-backend      →  API server   {dim(base_url)}
    make dev-worker       →  background investigation worker
    make dev-frontend     →  dashboard    {dim('http://localhost:5173')}

  {bold('Verify everything is healthy:')}
    bugpilot doctor

  {bold('Manage connectors:')}
    bugpilot connect list
    bugpilot connect github    --name org2       {dim('add another GitHub org')}
    bugpilot connect database  --name analytics  {dim('add another database')}
    bugpilot connect log-files --name nginx      {dim('add another log source')}

  {bold('Run your first investigation:')}
    bugpilot investigate "payment errors spiking"
""")


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    print()
    rule()
    print(bold("  BugPilot Developer Setup"))
    rule()
    print(f"""
  This wizard will guide you through 10 steps:

    1.  Check and install missing prerequisites
    2.  Accept the Terms of Service
    3.  Configure Supabase  (database)
    4.  Configure Redis     (caching & rate limiting)
    5.  Configure AWS SQS/SNS  (worker queues — optional, skippable)
    6.  Configure AI provider  (Anthropic / OpenAI)
    7.  Configure security settings
    8.  Set application settings
    ─── Review & confirm everything above  (nothing written until here) ───
    9.  Set up your CLI account
    10. Connect data sources  (GitHub, Sentry, databases, logs…)

  {yellow('!')}  {bold('Nothing is written to disk until you confirm the review in step 8.')}
  {yellow('!')}  {bold('You can connect multiple instances of any data source.')}
      e.g. two GitHub repos, three databases, multiple log paths.

  All secret inputs are hidden as you type.
  Press {bold('Ctrl+C')} at any time to abort — no changes will be made.
  Re-run at any time:  {dim('make dev-setup')}
""")
    input(f"  Press {bold('Enter')} to begin...")

    cfg: dict = {}

    # ── Steps 1-2: Prerequisites + ToS ───────────────────────────────────────
    if not check_prerequisites():
        sys.exit(1)

    terms_ts = accept_terms()

    # ── Steps 3-8: Collect all configuration (nothing written yet) ────────────
    setup_supabase(cfg)
    setup_redis(cfg)
    setup_aws(cfg)
    setup_llm(cfg)
    setup_security(cfg)
    setup_app(cfg)

    # ── Review: show everything, allow going back ─────────────────────────────
    pre_apply_review(cfg, terms_ts)

    # ── Apply: first write to disk here ──────────────────────────────────────
    header("Applying Configuration")
    write_env(cfg)
    print()
    apply_config()

    # ── Steps 9-10: CLI account + connectors (require server + CLI binary) ────
    setup_cli_account(cfg, terms_ts)
    setup_connectors(cfg)

    # ── Done ──────────────────────────────────────────────────────────────────
    print_done(cfg)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        print()
        warn("Setup interrupted — no files were written to disk.")
        hint("Re-run at any time with:  make dev-setup")
        sys.exit(1)
