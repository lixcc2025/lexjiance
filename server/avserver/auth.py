"""访问令牌：文件里只存 SHA-256 哈希（一行一个「名字:哈希」），泄露了也拿不到令牌本身。

  python -m avserver token add 某某律所      生成新令牌，只显示这一次
  python -m avserver token list / remove 名字
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from typing import Optional


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def load(path: str) -> dict[str, str]:
    """返回 {哈希: 名字}"""
    out: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or ":" not in line:
                    continue
                name, h = line.rsplit(":", 1)
                if len(h) == 64:
                    out[h.lower()] = name
    except FileNotFoundError:
        pass
    return out


def check(path: str, header: Optional[str]) -> Optional[str]:
    """Authorization 头 → 令牌名字；不对返回 None。逐个用常量时间比较"""
    if not header or not header.startswith("Bearer "):
        return None
    h = _hash(header[7:].strip())
    for known, name in load(path).items():
        if hmac.compare_digest(known, h):
            return name
    return None


def add(path: str, name: str) -> str:
    if ":" in name or "\n" in name:
        raise ValueError("名字里不能有冒号或换行")
    if name in load(path).values():
        raise ValueError(f"已经有叫「{name}」的令牌了")
    token = secrets.token_urlsafe(32)
    new = not os.path.exists(path)
    with open(path, "a", encoding="utf-8") as f:
        if new:
            f.write("# 访问令牌（只存哈希）。用 python -m avserver token add 名字 生成\n")
        f.write(f"{name}:{_hash(token)}\n")
    os.chmod(path, 0o600)
    return token


def remove(path: str, name: str) -> bool:
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return False
    keep = [l for l in lines if not l.strip() or l.startswith("#") or l.rsplit(":", 1)[0] != name]
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(keep)
    return len(keep) != len(lines)
