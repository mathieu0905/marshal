"""GitHub Actions CI/CD security threat model (Marshal P1 + P2).

Why a separate module from `SecurityHazard`: the path-prefix model matches a file
and emits one fixed lens. CI misconfigurations don't work that way — the danger is a
*combination* (untrusted trigger × {privileged runner | secret | write-permission |
open cross-repo dispatch}) and the pieces routinely sit **outside the 3-line diff
window** (exactly why node PR #649's `CROSS_REPO_TOKEN: ${{ secrets.* }}` on line ~32
was invisible to a diff-only scan that only saw the `runs-on:` line). So this reasons
over **whole workflow-file content**, and at **job granularity** — a push-only deploy
job must not raise a "PR can reach this runner" alarm, and an actor allowlist in *this
job's* `if:` (not a `github.actor` mention in some Slack message) must clear the alarm.

These are negative/adversarial properties (`invariant_able=False`): a review lens or a
dedicated external scanner (zizmor — see `cli ci-scan`) judges them; a roundtrip
proptest cannot express "this workflow is not exploitable". Bias is toward recall (it is
advisory — a missed HIGH is the #649 failure; a false positive costs one review glance).

Surfaced by node PR #649: Almanax caught a self-hosted-runner-on-`pull_request` HIGH plus
open privileged ephemeral deploy/destroy triggers; Marshal passed it blind.
"""
import re

CI_PREFIX = ".github/workflows/"

# Triggers that can run attacker-influenced code or execute in a privileged context.
# pull_request_target / workflow_run run in the BASE repo context WITH secrets and a
# write token (the classic "pwn request"). pull_request runs untrusted code on the
# runner — no secrets for FORK PRs, but secrets ARE available for same-repo-branch PRs.
_UNTRUSTED_TRIGGERS = ("pull_request_target", "workflow_run", "pull_request",
                       "issue_comment")
_PRIVILEGED_TRIGGERS = ("pull_request_target", "workflow_run")

# A GitHub-hosted DEFAULT runner label. Anything else (a custom org "larger" runner label
# like `ubuntu-latest-lx`, or `self-hosted`) cannot be proven ephemeral from the YAML
# alone — running an untrusted trigger on it warrants review. We deliberately cannot tell
# a GitHub-hosted larger runner from a self-hosted one by label; flagging conservatively
# is correct (the author confirms hosting out-of-band).
_DEFAULT_RUNNER = re.compile(
    r"^(ubuntu|windows|macos)-(latest|\d{2}\.\d{2}|\d{4}|\d{1,2})$", re.I)

_RUNS_ON = re.compile(r"runs-on:\s*(.+)", re.I)
_SECRET_REF = re.compile(r"\bsecrets\.", re.I)
_TOKEN_ENV = re.compile(r"\b[A-Z][A-Z0-9_]*TOKEN\b\s*:")   # `FOO_TOKEN:` env binding
_WRITE_PERM = re.compile(r"\b(id-token|contents|deployments|packages|"
                         r"pull-requests|issues|actions|security-events):\s*write\b", re.I)
_CROSS_REPO_DISPATCH = re.compile(
    r"repository[_-]dispatch|peter-evans/repository-dispatch|CROSS_REPO_TOKEN", re.I)
_BRANCH_GATE = re.compile(r"startsWith\(\s*github\.(ref|event\.ref)", re.I)
_ACTOR_GATE = re.compile(r"github\.actor", re.I)
_ENV_PROTECTION = re.compile(r"^\s{4,6}environment:\s*\S", re.I | re.M)
_EVENT_PIN = re.compile(r"github\.event_name\s*==\s*'([a-z_]+)'", re.I)
_PR_EVENTS = ("pull_request", "pull_request_target")
# Attacker-controlled free-text fields interpolated into a shell — injection sink. We
# scope to genuinely free-text fields (title/body/email); branch/ref names are constrained
# and commonly echoed, so excluding them avoids firing on every workflow.
_INJECTION = re.compile(
    r"\$\{\{[^}]*github\.event[^}]*\.(title|body|message|email)[^}]*\}\}", re.I)


def _runner_labels(text: str) -> list[str]:
    out = []
    for raw in _RUNS_ON.findall(text):
        v = raw.split("#", 1)[0].strip().strip("\"'")
        if not v or v.startswith("${{"):   # dynamic/expression runner — can't judge
            continue
        out.append(v)
    return out


def _is_custom_runner(label: str) -> bool:
    lab = label.strip()
    if lab.startswith("[") or "self-hosted" in lab.lower():
        return True
    return _DEFAULT_RUNNER.match(lab) is None


def _header_and_jobs(content: str):
    """Split a workflow into (header_text_before_jobs, [(job_name, job_text), ...]).

    Jobs are the keys directly under `jobs:` (indent of the first such key sets the job
    indent). Text-level parse — no YAML dependency, matching the pack's regex style."""
    lines = content.splitlines(keepends=True)
    jobs_idx = next((i for i, ln in enumerate(lines)
                     if re.match(r"^jobs:\s*$", ln)), None)
    if jobs_idx is None:
        return content, []
    header = "".join(lines[:jobs_idx])
    body = lines[jobs_idx + 1:]
    job_key = re.compile(r"^(\s+)([A-Za-z0-9_-]+):\s*$")
    indent = None
    jobs, cur_name, cur = [], None, []
    for ln in body:
        m = job_key.match(ln)
        if m and (indent is None or len(m.group(1)) == indent) and ln[:len(m.group(1))].strip() == "":
            if indent is None:
                indent = len(m.group(1))
            if cur_name is not None:
                jobs.append((cur_name, "".join(cur)))
            cur_name, cur = m.group(2), [ln]
        elif cur_name is not None:
            cur.append(ln)
    if cur_name is not None:
        jobs.append((cur_name, "".join(cur)))
    return header, jobs


def _job_if(job_text: str) -> str:
    """The job-level `if:` expression (indent ~4), including `if: |` continuations.
    Step-level `if:` (deeper indent) is excluded."""
    lines = job_text.splitlines()
    out, capturing, base = [], False, None
    for ln in lines:
        m = re.match(r"^(\s{2,8})if:\s*(.*)$", ln)
        if m and not capturing:
            base = len(m.group(1))
            out.append(m.group(2))
            capturing = True
            continue
        if capturing:
            ind = len(ln) - len(ln.lstrip())
            if ln.strip() and ind <= base:
                break
            out.append(ln.strip())
    return " ".join(out)


def _pr_reachable(jif: str, triggers: list) -> bool:
    """Can an untrusted pull_request actually reach this job? No, if the workflow has no
    PR trigger, or the job pins `event_name` to non-PR events (push/delete/schedule/…),
    or excludes pull_request, or restricts to main/devnet without a PR allowance."""
    if not any(t in _PR_EVENTS for t in triggers):
        return False
    pins = [p.lower() for p in _EVENT_PIN.findall(jif)]
    if pins and all(p not in _PR_EVENTS for p in pins):
        return False
    if re.search(r"github\.event_name\s*!=\s*'pull_request", jif, re.I):
        return False
    if re.search(r"github\.ref\s*==\s*'refs/heads/(main|devnet)'", jif, re.I) \
            and "pull_request" not in jif.lower():
        return False
    return True


def hazards_for_workflow(path: str, content: str) -> list[dict]:
    """Apply the CI threat model to one whole workflow file at job granularity."""
    header, jobs = _header_and_jobs(content)
    triggers = [t for t in _UNTRUSTED_TRIGGERS if re.search(rf"\b{t}\b", header)] \
        or [t for t in _UNTRUSTED_TRIGGERS if re.search(rf"\b{t}\b", content[:400])]
    privileged_trig = [t for t in _PRIVILEGED_TRIGGERS if t in triggers]

    out = []

    def add(hid, sev, title, prompt, evidence):
        out.append({"id": hid, "severity": sev, "title": title, "prompt": prompt,
                    "path": path, "evidence": evidence, "invariant_able": False})

    # File-level: a privileged trigger is dangerous regardless of which job consumes it.
    if privileged_trig:
        add("ci.privileged-untrusted-trigger", "high",
            "pull_request_target / workflow_run runs in a privileged context",
            ("默认怀疑:此 workflow 用 " + ",".join(privileged_trig) + " 触发,运行在 base 仓"
             "上下文且持有 secrets + write token。核查它是否检出并执行 PR 可控代码 "
             "(actions/checkout 带 ref: PR head / 不可信构建脚本)。若是 → pwn-request。"),
            {"triggers": privileged_trig})
    if _INJECTION.search(content):
        add("ci.script-injection", "high",
            "attacker-controlled event text interpolated into a shell step",
            ("检测到 ${{ github.event.*.(title|body|...) }} 等可被攻击者控制的自由文本疑似"
             "插入 run: shell → 命令注入。应改用 env: 中间变量,不要直接插值进 run。"),
            {})

    jobs = jobs or [("<file>", content)]
    for name, jt in jobs:
        jif = _job_if(jt)
        actor_gated = bool(_ACTOR_GATE.search(jif))
        has_dispatch = bool(_CROSS_REPO_DISPATCH.search(jt))
        branch_gated = bool(_BRANCH_GATE.search(jif))

        # Open privileged cross-repo dispatch: independent of PR-reachability — the risk
        # is that any contributor who can push/create the gated branch fires it.
        if has_dispatch and branch_gated and not actor_gated:
            add("ci.open-privileged-dispatch", "medium",
                "privileged cross-repo dispatch gated only by branch prefix (no actor allowlist)",
                (f"job `{name}` 触发跨仓特权自动化 (repository-dispatch / CROSS_REPO_TOKEN),仅靠"
                 "分支前缀门控、无 github.actor 白名单。任何能 push/删该前缀分支的人即可触发跨仓"
                 "部署/销毁 → 越权部署或 DoS。应加精确 actor 白名单或 environment 人工审批。"
                 "(node #649 deploy-feature/delete-feature 漏报点)"),
                {"job": name, "branch_gated": True, "actor_gated": False})

        # Untrusted-PR-reachable hazards: only for jobs a PR can actually reach (skips
        # push/delete/main-devnet-pinned jobs — fixes the pipeline.yml false positives).
        if not _pr_reachable(jif, triggers):
            continue
        custom = [r for r in _runner_labels(jt) if _is_custom_runner(r)]
        if custom:
            add("ci.custom-runner-on-untrusted-event", "high",
                "untrusted-triggerable job runs on a non-default (custom/self-hosted) runner",
                (f"job `{name}` 由不可信触发 ({','.join(triggers)}) 可达,且 runs-on 为非默认 "
                 "GitHub-hosted 标签: " + ",".join(custom) + "。若该 runner 是 self-hosted/网络"
                 "特权,恶意 PR 可在其上执行任意代码、窃取 runner 凭据。YAML 无法证明它是临时的 "
                 "GitHub-hosted 大 runner —— 须确认 hosting,或把不可信触发限回 ubuntu-latest。"
                 "(node #649 coverage.yml 漏报点)"),
                {"job": name, "runners": custom, "triggers": triggers})
        if (_SECRET_REF.search(jt) or _TOKEN_ENV.search(jt)) and not _ENV_PROTECTION.search(jt):
            add("ci.secret-exposed-to-untrusted-trigger", "high",
                "secrets/long-lived token reachable from an untrusted trigger w/o environment gate",
                (f"job `{name}` 由不可信触发 ({','.join(triggers)}) 可达,暴露 secrets / *_TOKEN "
                 "且无 environment: 保护。fork PR 默认拿不到 secrets,但**同仓分支 PR 能拿到** —— "
                 "较低信任的同仓贡献者 PR 代码即可外泄 CROSS_REPO_TOKEN/CODECOV_TOKEN 等。核查是否"
                 "应把该 job 限到 push/trusted 事件或加 environment 审批。"),
                {"job": name, "triggers": triggers})
        if _WRITE_PERM.search(jt) and privileged_trig:
            add("ci.permission-escalation", "medium",
                "write permissions granted on a privileged untrusted trigger",
                (f"job `{name}` 在特权不可信触发下授予 write 权限。核查最小权限:是否必要、是否应"
                 "收敛到具体 job、是否被不可信代码路径触及。"),
                {"job": name, "triggers": privileged_trig})

    return out


def scan_scope(scope: dict) -> tuple[list[dict], dict]:
    """Drive the threat model from a Marshal scope.

    Whole-file content comes from `scope['workflow_files']` = {path: content} (the skill
    reads changed workflows at PR head and passes them). If absent, falls back to scanning
    `diff_text` as a single blob — DEGRADED, since out-of-window constructs are invisible;
    the returned meta flags it so the gate records honestly (降级不谎报).
    """
    paths = [p for p in scope.get("diff_paths", []) if p.startswith(CI_PREFIX)]
    if not paths:
        return [], {"ci_workflow_paths": 0}
    files = scope.get("workflow_files") or {}
    meta = {"ci_workflow_paths": len(paths), "whole_file": bool(files),
            "degraded_no_whole_file": not files}
    hazards = []
    if files:
        for path, content in files.items():
            if path.startswith(CI_PREFIX):
                hazards.extend(hazards_for_workflow(path, content or ""))
    else:
        blob = scope.get("diff_text", "")
        for path in paths:
            hazards.extend(hazards_for_workflow(path, blob))
    return hazards, meta
