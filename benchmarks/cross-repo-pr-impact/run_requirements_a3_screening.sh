#!/usr/bin/env bash

set -uo pipefail

exec_root=${CINDER_A3_EXEC_ROOT:?set CINDER_A3_EXEC_ROOT to the prepared execution directory}
tox_runner=${CINDER_A3_TOX_RUNNER:?set CINDER_A3_TOX_RUNNER to the isolated tox executable}
result_root=${CINDER_A3_RESULT_ROOT:-$(pwd)/results/requirements-alembic-a3-screening-2026-08-24}
db_url=${CINDER_A3_DB_URL:-mysql+pymysql://openstack_citest:openstack_citest@127.0.0.1:33317/}

exec_root=$(realpath "$exec_root")
tox_runner=$(realpath "$tox_runner")
mkdir -p "$result_root"
result_root=$(realpath "$result_root")

repos=(heat ironic keystone nova placement)
if [[ -n ${CINDER_A3_REPOS:-} ]]; then
  IFS=, read -r -a repos <<<"$CINDER_A3_REPOS"
fi
arms=(before after)

declare -A commits=(
  [heat]=79feefc60e12fab1f40e53e40318091169696a72
  [ironic]=72d6dea279cf493d855953a404868fce1b39fbf1
  [keystone]=16afc813b7e6de727d8a91e065d7824b06e32925
  [nova]=fec26fb64baef2251bf547850ae71edfa6a7413d
  [placement]=0d503c6df70aa3049c29d4c2d8672703e068463e
)

declare -A tox_envs=(
  [heat]=py313
  [ironic]=py313
  [keystone]=py313
  [nova]=py313
  [placement]=functional-py313
)

declare -A tests=(
  [heat]=heat.tests.db.test_migrations.ModelsMigrationsSyncMysql.test_models_sync
  [ironic]=ironic.tests.unit.db.sqlalchemy.test_migrations.ModelsMigrationsSyncMysql.test_models_sync
  [keystone]=keystone.tests.unit.common.sql.test_upgrades.TestModelsSyncMySQL.test_models_sync
  [nova]='nova.tests.unit.db.(api|main).test_migrations.TestModelsSyncMySQL.test_models_sync'
  [placement]=placement.tests.functional.db.test_migrations.ModelsMigrationsSyncMysql.test_models_sync
)

failures=0
tox_pass_env=OS_TEST_DBAPI_ADMIN_CONNECTION
if [[ -n ${CFLAGS:-} ]]; then
  tox_pass_env+=,CFLAGS
fi
if [[ -n ${LDFLAGS:-} ]]; then
  tox_pass_env+=,LDFLAGS
fi

for arm in "${arms[@]}"; do
  constraints="$exec_root/requirements-a3-$arm/upper-constraints.txt"
  expected_version=1.17.2
  if [[ $arm == after ]]; then
    expected_version=1.18.0
  fi

  for repo in "${repos[@]}"; do
    work_dir="$exec_root/$repo-a3-$arm"
    prefix="$result_root/$repo-$arm"
    actual_commit=$(git -C "$work_dir" rev-parse HEAD)
    actual_root=$(git -C "$work_dir" rev-parse --show-toplevel)
    if [[ $actual_commit != "${commits[$repo]}" ]]; then
      printf '%s %s: commit mismatch: %s\n' "$repo" "$arm" "$actual_commit" | tee "$prefix-preflight.txt"
      failures=$((failures + 1))
      continue
    fi
    if [[ $(realpath "$actual_root") != "$work_dir" ]]; then
      printf '%s %s: worktree root mismatch: %s\n' "$repo" "$arm" "$actual_root" | tee "$prefix-preflight.txt"
      failures=$((failures + 1))
      continue
    fi

    {
      printf 'repository=%s\n' "$repo"
      printf 'arm=%s\n' "$arm"
      printf 'work_dir=%s\n' "$work_dir"
      printf 'git_root=%s\n' "$actual_root"
      printf 'commit=%s\n' "$actual_commit"
      printf 'tox_runner=%s\n' "$tox_runner"
      printf 'tox_env=%s\n' "${tox_envs[$repo]}"
      printf 'test=%s\n' "${tests[$repo]}"
      printf 'constraints=%s\n' "$constraints"
    } >"$prefix-context.txt"

    (
      cd "$work_dir" || exit 125
      OS_TEST_DBAPI_ADMIN_CONNECTION="$db_url" \
      TOX_CONSTRAINTS_FILE="$constraints" \
        /usr/bin/time -v -o "$prefix-time.txt" \
        "$tox_runner" -r \
        -x "testenv.pass_env=$tox_pass_env" \
        -e "${tox_envs[$repo]}" -- "${tests[$repo]}" \
        >"$prefix.log" 2>&1
    )
    status=$?
    printf '%s\n' "$status" >"$prefix-exit-status.txt"

    env_python="$work_dir/.tox/${tox_envs[$repo]}/bin/python"
    if [[ -x $env_python ]]; then
      "$env_python" - <<'PY' >"$prefix-versions.txt"
import alembic
import sqlalchemy
import sys

print(f"python={sys.version.split()[0]}")
print(f"alembic={alembic.__version__}")
print(f"sqlalchemy={sqlalchemy.__version__}")
PY
    fi

    actual_version=missing
    if [[ -f $prefix-versions.txt ]]; then
      actual_version=$(sed -n 's/^alembic=//p' "$prefix-versions.txt")
    fi

    if [[ $status -ne 0 || $actual_version != "$expected_version" ]]; then
      failures=$((failures + 1))
      printf '%s %s: failed status=%s alembic=%s expected=%s\n' \
        "$repo" "$arm" "$status" "$actual_version" "$expected_version"
    else
      printf '%s %s: passed alembic=%s\n' "$repo" "$arm" "$actual_version"
    fi
  done
done

exit "$failures"
