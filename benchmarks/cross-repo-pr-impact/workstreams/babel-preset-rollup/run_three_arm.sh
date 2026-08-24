#!/usr/bin/env bash

set -u -o pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd "$script_dir/../../../.." && pwd)
work_root=${1:-$repo_root/.work/babel-preset-rollup}
output_dir=${2:-$repo_root/benchmarks/cross-repo-pr-impact/results/babel-preset-rollup-local-three-arm-2026-08-24}
node_bin=${NODE_BIN:-/home/zhihao/.nvm/versions/node/v6.17.1/bin/node}
npm_bin=${NPM_BIN:-npm}
probe="$script_dir/probe.js"
package_cache="$work_root/package-cache"

mkdir -p "$work_root" "$output_dir" "$package_cache"

prepare_target() {
    version=$1
    archive="$package_cache/babel-preset-es2015-rollup-$version.tgz"
    unpacked="$package_cache/target-$version"

    if [ ! -f "$archive" ]; then
        packed=$(
            cd "$package_cache" &&
                "$npm_bin" pack "babel-preset-es2015-rollup@$version" --silent
        )
        if [ "$package_cache/$packed" != "$archive" ]; then
            mv "$package_cache/$packed" "$archive"
        fi
    fi
    if [ ! -d "$unpacked/package" ]; then
        mkdir -p "$unpacked"
        tar -xzf "$archive" -C "$unpacked"
    fi
}

prepare_arm() {
    arm=$1
    source_version=$2
    modifier_version=$3
    target_version=$4
    target_metadata_version=$5
    arm_dir="$work_root/$arm"

    mkdir -p "$arm_dir"
    if [ ! -f "$arm_dir/package.json" ]; then
        (cd "$arm_dir" && "$npm_bin" init -y >/dev/null)
    fi
    "$npm_bin" install --prefix "$arm_dir" --ignore-scripts --no-audit \
        --no-fund --save-exact \
        babel-core@6.13.2 \
        "babel-preset-es2015@$source_version" \
        "modify-babel-preset@$modifier_version" \
        babel-plugin-external-helpers@6.8.0 \
        require-relative@0.8.7 \
        >"$output_dir/$arm-install.log" 2>&1

    mkdir -p "$arm_dir/target"
    cp "$package_cache/target-$target_version/package/index.js" \
        "$arm_dir/target/index.js"
    jq --arg version "$target_metadata_version" '.version = $version' \
        "$package_cache/target-$target_version/package/package.json" \
        >"$arm_dir/target/package.json"
}

run_arm() {
    arm=$1
    expected=$2
    arm_dir="$work_root/$arm"
    start_time=$(date +%s)

    (
        cd "$arm_dir" &&
            NODE_PATH="$arm_dir/node_modules" \
                "$node_bin" "$probe" "$arm_dir/target"
    ) >"$output_dir/$arm.log" 2>&1
    exit_code=$?
    end_time=$(date +%s)
    if [ "$exit_code" -eq 0 ]; then
        observed=pass
    else
        observed=fail
    fi

    printf '%s\n' "$exit_code" >"$output_dir/$arm.exit"
    printf '%s\t%s\t%s\t%s\t%s\n' \
        "$arm" "$expected" "$observed" "$exit_code" \
        "$((end_time - start_time))" >>"$output_dir/run-results.tsv"
}

prepare_target 1.1.1
prepare_target 1.2.0

# 下游项目实际声明 ^1.1.1；该发布物直接操作插件数组，不使用 modify-babel-preset。
prepare_arm A0 6.13.0 1.0.0 1.1.1 1.1.1
prepare_arm A1 6.13.1 1.0.0 1.1.1 1.1.1
# A2 使用 1.2.0 的代码和修复依赖，但故意保留 1.1.1 版本字段。
prepare_arm A2 6.13.1 2.1.1 1.2.0 1.1.1
# 贡献隔离：只换代码、只提供新依赖或只改发布编号都不足以恢复。
prepare_arm CODE_ONLY 6.13.1 1.0.0 1.2.0 1.1.1
prepare_arm DEPENDENCY_ONLY 6.13.1 2.1.1 1.1.1 1.1.1
prepare_arm VERSION_ONLY 6.13.1 1.0.0 1.1.1 1.2.0
prepare_arm RELEASE_1_2_0 6.13.1 2.1.1 1.2.0 1.2.0

printf 'arm\texpected\tobserved\texit_code\tduration_seconds\n' \
    >"$output_dir/run-results.tsv"
"$node_bin" --version >"$output_dir/node-version.txt" 2>&1
"$npm_bin" --version >"$output_dir/npm-version.txt" 2>&1

run_arm A0 pass
run_arm A1 fail
run_arm A2 pass
run_arm CODE_ONLY fail
run_arm DEPENDENCY_ONLY fail
run_arm VERSION_ONLY fail
run_arm RELEASE_1_2_0 pass
