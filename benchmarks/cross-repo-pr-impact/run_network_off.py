#!/usr/bin/env python3
"""Exec a command under an inherited seccomp filter that denies networking."""

from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import errno
import json
import os
import socket
from pathlib import Path


SCMP_ACT_ALLOW = 0x7FFF0000
SCMP_ACT_ERRNO = 0x00050000
DENIED_SYSCALLS = (
    "socket", "socketpair", "connect", "bind", "listen", "accept", "accept4",
    "sendto", "recvfrom", "sendmsg", "recvmsg", "shutdown", "getsockname",
    "getpeername", "setsockopt", "getsockopt",
)


def install_network_filter() -> None:
    library_name = ctypes.util.find_library("seccomp")
    if not library_name:
        raise RuntimeError("libseccomp is unavailable")
    library = ctypes.CDLL(library_name, use_errno=True)
    library.seccomp_init.argtypes = [ctypes.c_uint32]
    library.seccomp_init.restype = ctypes.c_void_p
    library.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    library.seccomp_syscall_resolve_name.restype = ctypes.c_int
    library.seccomp_rule_add.argtypes = [
        ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint,
    ]
    library.seccomp_rule_add.restype = ctypes.c_int
    library.seccomp_load.argtypes = [ctypes.c_void_p]
    library.seccomp_load.restype = ctypes.c_int
    library.seccomp_release.argtypes = [ctypes.c_void_p]

    context = library.seccomp_init(SCMP_ACT_ALLOW)
    if not context:
        raise OSError(ctypes.get_errno(), "seccomp_init failed")
    try:
        action = SCMP_ACT_ERRNO | errno.EPERM
        for name in DENIED_SYSCALLS:
            number = library.seccomp_syscall_resolve_name(name.encode("ascii"))
            if number < 0:
                continue
            result = library.seccomp_rule_add(context, action, number, 0)
            if result:
                raise OSError(-result, f"seccomp_rule_add failed for {name}")
        result = library.seccomp_load(context)
        if result:
            raise OSError(-result, "seccomp_load failed")
    finally:
        library.seccomp_release(context)


def probe() -> dict[str, object]:
    try:
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    except OSError as exc:
        return {
            "schema_version": "1.0",
            "mechanism": "libseccomp_inherited_syscall_filter",
            "socket_probe_blocked": exc.errno == errno.EPERM,
            "socket_probe_errno": exc.errno,
            "denied_syscalls": list(DENIED_SYSCALLS),
        }
    return {
        "schema_version": "1.0",
        "mechanism": "libseccomp_inherited_syscall_filter",
        "socket_probe_blocked": False,
        "socket_probe_errno": None,
        "denied_syscalls": list(DENIED_SYSCALLS),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe-output", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("a command is required after --")
    install_network_filter()
    result = probe()
    args.probe_output.parent.mkdir(parents=True, exist_ok=True)
    args.probe_output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if not result["socket_probe_blocked"]:
        raise RuntimeError("network isolation probe was not blocked")
    os.environ["MARSHAL_NETWORK_CONTROL"] = result["mechanism"]
    os.execvp(command[0], command)
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
