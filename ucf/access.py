"""This PC's own read-only key to the (private) H-Labs repo on GitHub (2026-11-28).

Each PC makes its OWN SSH key here (never shown, never sent anywhere); the owner adds only the PUBLIC half to GitHub ->
H-Labs -> Settings -> Deploy keys, named after the PC, WITHOUT write access. After that every update of this PC (Studio
button, menu 8, setup) pulls with that key. A lost / stolen PC or a person who leaves: delete that one deploy key on
GitHub - the other PCs keep working. The key file stays in the user's own folder (~/.config/umf), not in the H Labs folder,
so copying the H Labs folder to another PC does not copy the access.

The remote uses ssh.github.com on port 443 (works on networks that block SSH port 22).
"""
import os
import platform
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KEY = Path.home() / ".config" / "umf" / "hlabs_github_key"
REPO = "haseeb109/H-Labs"
SSH_URL = f"ssh://git@ssh.github.com:443/{REPO}.git"


def _git(*a, timeout=60):
    try:
        return subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        return subprocess.CompletedProcess(a, 1, "", str(e))


def _tool(name):
    """ssh-keygen / ssh: on PATH, else the copy inside Git for Windows (<git>/usr/bin)."""
    p = shutil.which(name)
    if p:
        return p
    g = shutil.which("git")
    if g:
        for base in (Path(g).resolve().parent.parent, Path(g).resolve().parent.parent.parent):
            c = base / "usr" / "bin" / (name + (".exe" if os.name == "nt" else ""))
            if c.exists():
                return str(c)
    return None


def pc_name():
    return (os.environ.get("COMPUTERNAME") or platform.node() or "pc")[:40]


def public_key():
    p = KEY.with_suffix(".pub")
    return p.read_text(encoding="utf-8").strip() if p.exists() else ""


def make_key():
    """Create this PC's key once (an existing one is kept). -> public key text to add on GitHub."""
    if not KEY.exists():
        kg = _tool("ssh-keygen")
        if not kg:
            raise RuntimeError("ssh-keygen not found (it comes with Git) - run Setup.bat once, then try again")
        KEY.parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run([kg, "-q", "-t", "ed25519", "-N", "", "-C", f"hlabs-{pc_name()}", "-f", str(KEY)],
                           capture_output=True, text=True, timeout=60)
        if r.returncode or not KEY.exists():
            raise RuntimeError(f"could not make the key: {(r.stderr or r.stdout).strip()[-200:]}")
        try:
            os.chmod(KEY, 0o600)
        except OSError:
            pass
    use_key()
    return public_key()


def use_key():
    """Point this clone at GitHub over SSH with this PC's key (only when the key exists)."""
    if not KEY.exists() or not (ROOT / ".git").exists():
        return False
    ssh = _tool("ssh") or "ssh"
    cmd = (f'"{Path(ssh).as_posix()}" -i "{KEY.as_posix()}" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new '
           f'-o BatchMode=yes -o ConnectTimeout=20')
    _git("config", "core.sshCommand", cmd)
    _git("remote", "set-url", "origin", SSH_URL)
    return True


def status():
    """-> {"key": bool, "pc": name, "public_key": str, "remote": url, "ok": bool | None, "message": str}."""
    url = _git("remote", "get-url", "origin").stdout.strip()
    out = {"key": KEY.exists(), "pc": pc_name(), "public_key": public_key(), "remote": url, "ok": None, "message": ""}
    return out


def test():
    """Can this PC read the repo right now? -> (ok, message)."""
    r = _git("ls-remote", "--heads", "origin", "main", timeout=60)
    if r.returncode == 0 and r.stdout.strip():
        return True, "this PC can read H-Labs on GitHub - updates work"
    err = (r.stderr or r.stdout).strip().splitlines()
    err = err[-1] if err else "no answer"
    if "Permission denied" in err or "publickey" in err:
        return False, ("GitHub does not know this PC's key yet - add the key below on GitHub (H-Labs > Settings > Deploy keys, "
                       "name: " + pc_name() + ", write access OFF)")
    if "Repository not found" in err or "could not read Username" in err:
        return False, "the repo is private and this PC has no key yet - press 'Make this PC's key' and add it on GitHub"
    return False, "GitHub could not be reached: " + err[:160]
