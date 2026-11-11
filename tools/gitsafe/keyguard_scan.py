#!/usr/bin/env python3
"""全历史密钥扫描（无外部依赖，只需 git）。

用法:
    python keyguard_scan.py <本地仓库路径> [--json out.json]
    python keyguard_scan.py <https://github.com/user/repo>   # 自动浅克隆到 tmp\_scan

扫描范围: 所有分支、所有 tag、已删除文件、commit message。
输出:   命中列表（文件 / commit / 规则 / 脱敏后的值）。
"""
import json
import os
import re
import subprocess
import sys
import tempfile

# (规则名, 正则, 是否高置信)
RULES = [
    ("OpenAI",            r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_\-]{20,}", True),
    ("Anthropic",         r"\bsk-ant-[A-Za-z0-9_\-]{20,}", True),
    ("AWS AccessKey",     r"\b(?:AKIA|ASIA|ABIA|ACCA)[0-9A-Z]{16}\b", True),
    ("AWS Secret",        r"(?i)aws.{0,20}['\"]([A-Za-z0-9/+=]{40})['\"]", False),
    ("GitHub Token",      r"\bgh[pousr]_[A-Za-z0-9]{36,}\b", True),
    ("GitHub FineGrain",  r"\bgithub_pat_[A-Za-z0-9_]{40,}\b", True),
    ("Google API Key",    r"\bAIza[0-9A-Za-z_\-]{35}\b", True),
    ("GCP ServiceAcct",   r'"type"\s*:\s*"service_account"', True),
    ("Slack Token",       r"\bxox[baprs]-[A-Za-z0-9\-]{10,}", True),
    ("Stripe Live",       r"\b(?:sk|rk)_live_[A-Za-z0-9]{20,}", True),
    ("Stripe Test",       r"\bsk_test_[A-Za-z0-9]{20,}", False),
    ("Telegram Bot",      r"\b\d{8,10}:AA[A-Za-z0-9_\-]{33}\b", True),
    ("阿里云 AccessKey",   r"\bLTAI[A-Za-z0-9]{12,20}\b", True),
    ("腾讯云 SecretId",    r"\bAKID[A-Za-z0-9]{13,40}\b", True),
    ("七牛",              r"(?i)qiniu.{0,20}['\"]([A-Za-z0-9_\-]{40})['\"]", False),
    ("微信 AppSecret",    r"(?i)app_?secret\s*[:=]\s*['\"]([0-9a-f]{32})['\"]", True),
    ("JWT",               r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}", False),
    ("Private Key Block", r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----", True),
    ("URL 内嵌密码",       r"\b[a-z][a-z0-9+.\-]*://[^\s:/@\"']+:[^\s:/@\"']{6,}@[^\s/\"']+", False),
    ("通用赋值(低置信)",   r"(?i)(?:api[_-]?key|secret|token|passwd|password|access[_-]?key)\s*[:=]\s*['\"]([A-Za-z0-9_\-/+.]{20,})['\"]", False),
]

# 明显是占位符 / 模板 / 示例的，跳过
PLACEHOLDER = re.compile(
    r"(?i)(your[_-]?|xxx|placeholder|example|dummy|sample|change[_-]?me|"
    r"<[^>]*>|\$\{|\{\{|\.\.\.|redacted|fake|test[_-]?only|"
    r"^0+$|^a{8,}$|^x{8,}$)"
)

SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip",
            ".gz", ".tgz", ".7z", ".rar", ".woff", ".woff2", ".ttf", ".eot",
            ".mp4", ".mp3", ".wav", ".bin", ".exe", ".dll", ".so", ".dylib",
            ".pyc", ".pack", ".idx"}


def sh(args, cwd=None):
    return subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT)


def mask(s):
    s = s.strip()
    if len(s) <= 12:
        return s[:4] + "***"
    return s[:6] + "..." + s[-4:] + f" (len={len(s)})"


def resolve_target(target):
    """本地路径直接用；URL 则浅克隆。返回 (路径, 是否临时)。"""
    if os.path.isdir(target) and os.path.exists(os.path.join(target, ".git")):
        return target, False
    if re.match(r"^(https?://|git@)", target):
        base = re.sub(r"\.git$", "", target.rstrip("/")).split("/")[-1]
        dest = os.path.join(tempfile.gettempdir(), "_scan_" + base)
        if os.path.exists(dest):
            print(f"[i] 复用已存在克隆: {dest}")
            return dest, False
        print(f"[i] 克隆 {target} -> {dest}")
        r = sh(["git", "clone", "--quiet", target, dest])
        if r.returncode != 0:
            sys.exit("[!] 克隆失败:\n" + r.stdout.decode("utf-8", "replace")[-1500:])
        return dest, False
    sys.exit(f"[!] 不是 git 仓库，也不是可克隆 URL: {target}")


def scan(repo):
    findings = []
    # 1) 遍历所有 commit 的 diff + commit message，流式处理
    proc = subprocess.Popen(
        ["git", "-C", repo, "log", "--all", "-p", "--full-index",
         "--pretty=format:@@COMMIT@@%H%x09%an%x09%ad%x09%s", "--date=short",
         "--no-color", "--no-ext-diff", "--diff-filter=ACMRDT"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0,
    )
    cur = {"sha": "?", "author": "?", "date": "?", "subject": "?"}
    cur_file = "?"
    seen = set()
    for raw in proc.stdout:
        line = raw.decode("utf-8", "replace").rstrip("\n")
        if line.startswith("@@COMMIT@@"):
            parts = line[len("@@COMMIT@@"):].split("\t")
            while len(parts) < 4:
                parts.append("")
            cur = {"sha": parts[0], "author": parts[1],
                   "date": parts[2], "subject": parts[3]}
            continue
        if line.startswith("+++ b/"):
            cur_file = line[6:]
            continue
        if line.startswith(("--- a/", "diff --git", "index ", "new file",
                            "deleted file", "similarity", "rename ",
                            "old mode", "new mode", "Binary files")):
            continue
        # 只看新增行（含 commit message 通过 @@ 之前的头处理不到，下面单独扫）
        if not line.startswith("+"):
            continue
        body = line[1:]
        if not body.strip():
            continue
        if os.path.splitext(cur_file)[1].lower() in SKIP_EXT:
            continue
        for name, pat, confident in RULES:
            for m in re.finditer(pat, body):
                hit = m.group(0)
                val = m.group(1) if m.groups() else hit
                if PLACEHOLDER.search(val) or PLACEHOLDER.search(hit):
                    continue
                key = (name, cur["sha"], cur_file, hit[:80])
                if key in seen:
                    continue
                seen.add(key)
                findings.append({
                    "rule": name, "confident": confident,
                    "value": mask(val), "file": cur_file,
                    "commit": cur["sha"][:12], "date": cur["date"],
                    "author": cur["author"], "subject": cur["subject"][:60],
                })
    proc.stdout.close()
    proc.wait()

    # 2) 扫 commit message 本身
    log = sh(["git", "-C", repo, "log", "--all",
              "--pretty=format:%H%x09%ad%x09%s%x09%b", "--date=short"])
    for ln in log.stdout.decode("utf-8", "replace").splitlines():
        if not ln.strip():
            continue
        for name, pat, confident in RULES:
            for m in re.finditer(pat, ln):
                hit = m.group(0)
                val = m.group(1) if m.groups() else hit
                if PLACEHOLDER.search(val):
                    continue
                key = (name, ln[:12], "<commit-message>", hit[:80])
                if key in seen:
                    continue
                seen.add(key)
                findings.append({
                    "rule": name, "confident": confident,
                    "value": mask(val), "file": "<commit-message>",
                    "commit": ln.split("\t")[0][:12],
                    "date": ln.split("\t")[1] if "\t" in ln else "?",
                    "author": "?", "subject": ln.split("\t")[2][:60] if ln.count("\t") > 1 else "",
                })

    # 3) 当前工作区里不该被追踪的文件
    tracked = sh(["git", "-C", repo, "ls-files"])
    bad = []
    for f in tracked.stdout.decode("utf-8", "replace").splitlines():
        base = os.path.basename(f).lower()
        if (base in (".env", ".env.local", ".env.production", "secrets.json",
                     "credentials", ".npmrc", ".pypirc", "id_rsa", "id_ed25519")
                or base.endswith((".pem", ".p12", ".pfx", ".keystore", ".jks"))
                or "secret" in base or "credential" in base):
            bad.append(f)
    return findings, bad


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    target = sys.argv[1]
    out_json = None
    if "--json" in sys.argv:
        out_json = sys.argv[sys.argv.index("--json") + 1]

    repo, _ = resolve_target(target)
    print(f"[i] 扫描仓库: {repo}")
    n_commit = sh(["git", "-C", repo, "rev-list", "--all", "--count"]).stdout.decode().strip()
    n_branch = sh(["git", "-C", repo, "branch", "-a"]).stdout.decode().count("\n") + 1
    print(f"[i] 提交数: {n_commit}   分支/远端引用: ~{n_branch}\n")

    findings, bad_tracked = scan(repo)

    conf = [f for f in findings if f["confident"]]
    weak = [f for f in findings if not f["confident"]]

    if conf:
        print(f"=== 高置信命中 {len(conf)} 条（需立即轮换）===")
        for f in conf:
            print(f"  [{f['rule']}] {f['value']}")
            print(f"      {f['file']}  @{f['commit']} {f['date']} {f['author']}")
    else:
        print("=== 高置信命中: 0 条 ===")

    if weak:
        print(f"\n=== 低置信/需人工判断 {len(weak)} 条 ===")
        for f in weak[:40]:
            print(f"  [{f['rule']}] {f['value']}  {f['file']} @{f['commit']}")
        if len(weak) > 40:
            print(f"  ...另有 {len(weak) - 40} 条，见 JSON")

    if bad_tracked:
        print(f"\n=== 已被 git 追踪的敏感文件 {len(bad_tracked)} 个 ===")
        for f in bad_tracked:
            print(f"  {f}")

    if out_json:
        with open(out_json, "w", encoding="utf-8") as fh:
            json.dump({"repo": repo, "findings": findings,
                       "tracked_suspicious": bad_tracked}, fh,
                      ensure_ascii=False, indent=2)
        print(f"\n[i] 详细结果: {out_json}")


if __name__ == "__main__":
    main()