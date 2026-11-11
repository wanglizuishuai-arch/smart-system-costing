#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gitsafe pre-commit: 拦截暂存区里的 API key / 凭证 / 私钥。

只看 git diff --cached 的新增行，速度毫秒级，不扫历史。
由 .git/hooks/pre-commit 调用，无需手动运行。

退出码 1 = 拦截。误报可 git commit --no-verify 跳过。
"""
import os
import re
import subprocess
import sys

# (规则名, 正则, 第几个捕获组是真值, 是否高置信)
RULES = [
    ("OpenAI Key",         r"\bsk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_\-]{20,}", 0, True),
    ("Anthropic Key",      r"\bsk-ant-[A-Za-z0-9_\-]{20,}", 0, True),
    ("AWS AccessKey",      r"\b(?:AKIA|ASIA|ABIA|ACCA)[0-9A-Z]{16}\b", 0, True),
    ("AWS SecretKey",      r"(?i)aws[_.\-\s]{0,20}secret[_.\-\s]{0,20}['\"]([A-Za-z0-9/+=]{40})['\"]", 1, True),
    ("GitHub Token",       r"\bgh[pousr]_[A-Za-z0-9]{36,}\b", 0, True),
    ("GitHub FineGrain",   r"\bgithub_pat_[A-Za-z0-9_]{40,}\b", 0, True),
    ("Google API Key",     r"\bAIza[0-9A-Za-z_\-]{35}\b", 0, True),
    ("GCP ServiceAccount", r'"type"\s*:\s*"service_account"', 0, True),
    ("Slack Token",        r"\bxox[baprs]-[A-Za-z0-9\-]{10,}", 0, True),
    ("Stripe Live Key",    r"\b(?:sk|rk)_live_[A-Za-z0-9]{20,}", 0, True),
    ("阿里云 AccessKey",    r"\bLTAI[A-Za-z0-9]{12,20}\b", 0, True),
    ("腾讯云 SecretId",     r"\bAKID[A-Za-z0-9]{13,40}\b", 0, True),
    ("微信 AppSecret",     r"(?i)app_?secret\s*[:=]\s*['\"]([0-9a-f]{32})['\"]", 1, True),
    ("Telegram BotToken",  r"\b\d{8,10}:AA[A-Za-z0-9_\-]{33}\b", 0, True),
    ("Private Key Block",  r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY-----", 0, True),
    ("JWT",                r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}", 0, False),
    ("带密码的连接串",       r"\b[a-z][a-z0-9+.\-]{1,15}://[^\s:/@\"']{1,32}:[^\s:/@\"']{6,}@[^\s/\"']+", 0, False),
    ("通用赋值",            r"(?i)(?:api[_-]?key|apikey|secret[_-]?key|access[_-]?token|auth[_-]?token|passwd|password)\s*[:=]\s*['\"]([A-Za-z0-9_\-/+.]{20,})['\"]", 1, False),
]

# 以下情况视为占位符/示例，放行
PLACEHOLDER = re.compile(
    r"(?i)(your[_-]?|xxx+|placeholder|example|dummy|sample|change[_-]?me|"
    r"replace[_-]?me|todo|fixme|redacted|fake|mock|"
    r"^\$\{|\{\{|<[^>]{0,40}>|\.\.\.|"
    r"^0{8,}$|^a{8,}$|^x{8,}$|^1{8,}$|"
    r"process\.env|os\.environ|getenv|System\.getenv|"
    r"import\.meta\.env|secrets\.|ENV\[)"
)

SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip",
            ".gz", ".tgz", ".7z", ".rar", ".woff", ".woff2", ".ttf", ".eot",
            ".mp4", ".mp3", ".wav", ".bin", ".exe", ".dll", ".so", ".dylib",
            ".pyc", ".pack", ".idx", ".lock", ".map", ".svg"}

# 文件名命中即拦截（不管内容）
FORBIDDEN_NAMES = {
    ".env", ".env.local", ".env.production", ".env.development",
    "secrets.json", "secrets.yml", "secrets.yaml", "credentials",
    "credentials.json", ".npmrc", ".pypirc", ".netrc",
    "id_rsa", "id_ed25519", "id_ecdsa", "id_dsa",
}
FORBIDDEN_EXT = {".pem", ".p12", ".pfx", ".keystore", ".jks", ".ovpn", ".kdbx"}

ALLOW_MARK = "gitsafe:allow-line"


def git(*args):
    return subprocess.run(
        ["git"] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        encoding="utf-8", errors="replace",
    ).stdout


def mask(s):
    s = s.strip()
    if len(s) <= 12:
        return s[:3] + "***"
    return s[:6] + "..." + s[-4:] + f" [len={len(s)}]"


def parse_diff(diff):
    """产出 (file, lineno, text) —— 只含新增行。"""
    cur = None
    newno = 0
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            cur = line[6:]
            continue
        if line.startswith("+++ "):
            cur = line[4:].strip()
            continue
        m = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
        if m:
            newno = int(m.group(1))
            continue
        if cur is None:
            continue
        if line.startswith("+"):
            yield cur, newno, line[1:]
            newno += 1
        elif line.startswith(" "):
            newno += 1
        # '-' 行不占新行号


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    staged = [f for f in git("diff", "--cached", "--name-only", "--diff-filter=ACMR").splitlines() if f.strip()]
    if not staged:
        return 0

    problems = []

    # ---- 1. 文件名黑名单 ----
    for f in staged:
        base = os.path.basename(f).lower()
        ext = os.path.splitext(base)[1]
        if base in FORBIDDEN_NAMES or ext in FORBIDDEN_EXT \
                or "secret" in base or "credential" in base:
            problems.append((f, 0, "文件名", f"{base} 属于不应入库的文件", True))

    # ---- 2. 内容扫描 ----
    diff = git("diff", "--cached", "--unified=0", "--diff-filter=ACMR", "--no-color", "--no-ext-diff")
    for file, lineno, text in parse_diff(diff):
        if os.path.splitext(file)[1].lower() in SKIP_EXT:
            continue
        if not text.strip() or ALLOW_MARK in text:
            continue
        for name, pat, grp, confident in RULES:
            for m in re.finditer(pat, text):
                raw = m.group(0)
                val = m.group(grp) if grp and m.groups() else raw
                if not val:
                    continue
                if PLACEHOLDER.search(val) or PLACEHOLDER.search(raw):
                    continue
                problems.append((file, lineno, name, mask(val), confident))
                break

    if not problems:
        return 0

    hard = [p for p in problems if p[4]]
    soft = [p for p in problems if not p[4]]

    bar = "=" * 68
    print(f"\n{bar}")
    print("  gitsafe 拦截了这次提交：发现疑似密钥 / 凭证")
    print(bar)
    if hard:
        print("\n  【高置信 · 必须处理】")
        for f, ln, rule, val, _ in hard:
            loc = f"{f}:{ln}" if ln else f
            print(f"    {loc:38s} [{rule}] {val}")
    if soft:
        print("\n  【需人工确认】")
        for f, ln, rule, val, _ in soft[:10]:
            loc = f"{f}:{ln}" if ln else f
            print(f"    {loc:38s} [{rule}] {val}")
        if len(soft) > 10:
            print(f"    ...另有 {len(soft) - 10} 条")

    print(f"\n{'-' * 68}")
    print("  怎么处理：")
    print("    1. 把值换成环境变量读取，代码里只留 os.environ['X'] / process.env.X")
    print("    2. 若文件本就该在本地：git restore --staged <文件> 并写进 .gitignore")
    print("    3. 确认是误报（文档示例、假数据）：git commit --no-verify")
    print(f"{bar}\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())