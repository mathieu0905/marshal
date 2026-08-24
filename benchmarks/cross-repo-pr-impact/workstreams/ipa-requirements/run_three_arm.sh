#!/usr/bin/env bash

set -u -o pipefail

work_root=${1:-/home/zhihao/hdd/ipa-requirements-work}
output_dir=${2:-/home/zhihao/hdd/marshal/benchmarks/cross-repo-pr-impact/results/ipa-requirements-local-three-arm-2026-08-24}

python_bin="$work_root/venv/bin/python"
check_script="$work_root/req-old/playbooks/files/project-requirements-change.py"

mkdir -p "$output_dir"

run_arm() {
    arm=$1
    source_dir=$2
    requirements_dir=$3

    start_time=$(date +%s)
    "$python_bin" "$check_script" "$source_dir" master \
        --reqs "$requirements_dir" >"$output_dir/$arm.log" 2>&1
    exit_code=$?
    end_time=$(date +%s)

    printf '%s\n' "$exit_code" >"$output_dir/$arm.exit"
    printf '%s\t%s\t%s\t%s\n' \
        "$arm" "$exit_code" "$((end_time - start_time))" \
        "$source_dir" >>"$output_dir/run-results.tsv"
}

printf 'arm\texit_code\tduration_seconds\tsource_dir\n' \
    >"$output_dir/run-results.tsv"

"$python_bin" --version >"$output_dir/python-version.txt" 2>&1
git -C "$work_root/ipa-a0" rev-parse HEAD >"$output_dir/a0-source-commit.txt"
git -C "$work_root/ipa-a1" rev-parse HEAD >"$output_dir/a1-a2-source-commit.txt"
git -C "$work_root/req-old" rev-parse HEAD >"$output_dir/a0-a1-requirements-commit.txt"
git -C "$work_root/req-a2" diff >"$output_dir/a2-requirements.patch"

run_arm A0 "$work_root/ipa-a0" "$work_root/req-old"
run_arm A1 "$work_root/ipa-a1" "$work_root/req-old"
run_arm A2 "$work_root/ipa-a1" "$work_root/req-a2"

