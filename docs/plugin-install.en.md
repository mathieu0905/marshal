# Installing the Marshal Plugin

Marshal's consumer-side quality gate, packaged as a Claude Code plugin. It runs risk-tiering + invariant gating + adversarial review over a read-only invariant snapshot. The first run auto-bootstraps everything it needs.

> 中文版见 [`plugin-install.md`](plugin-install.md).

## Prerequisites

- **Claude Code** (for the `--plugin-dir` zip method: v2.1.128+)
- **python3 ≥ 3.11** on PATH
- **uv** — *not required up front; the plugin auto-installs it on first run* (single-user install, no root). The only hard blocks are `python3 < 3.11` or a Claude Code too old to inject `${CLAUDE_PLUGIN_ROOT}`.

## Install — pick one

### Option 1 · GitHub

```
/plugin marketplace add shawhanken/marshal
/plugin install marshal
```

### Option 2 · Local folder / zip (no GitHub)

```bash
unzip marshal-plugin-0.0.2.zip -d ~/marshal-plugin
```

```
/plugin marketplace add ~/marshal-plugin
/plugin install marshal
```

Point `marketplace add` at the unzipped directory (the one containing `.claude-plugin/`). The plugin resolves locally — no network to github.com.

### Option 3 · Direct load, no marketplace (Claude Code ≥ v2.1.128)

```bash
claude --plugin-dir ~/marshal-plugin/plugins/marshal
```

## First run

```
/marshal
```

On first run the plugin auto-detects your environment and self-repairs: installs `uv` if missing, builds the env (`uv sync`), and seeds the invariant snapshot into a local DB. You will see a notice if it is installing `uv` for you.

## Usage

```
/marshal                       # gate the current branch diff
/marshal <repo> <PR#>          # gate a specific repo's PR, e.g. /marshal runner 42
/marshal <PR-URL>              # gate by full PR URL
```

## Updating

```
/plugin update
```

Pulls a refreshed invariant set after a maintainer release (the version bump triggers an automatic re-seed). For Option 2, replace your local folder with the newer zip, then `/plugin update`.

## Notes

- **Read-only / one-way.** You consume a published invariant snapshot. A local `/marshal ratchet` stays in *your* DB and does **not** flow back to the team; new team-wide invariants ship via maintainer releases.
- **Troubleshooting.** If `/marshal` reports `blocked`, the message names the cause: `python3>=3.11` (install Python 3.11+), `CLAUDE_PLUGIN_ROOT` (update Claude Code), or `uv-install-failed` / `seed-failed` (check the doctor stderr it prints).
