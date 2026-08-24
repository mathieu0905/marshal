#!/usr/bin/env bash

set -uo pipefail

if [[ $# -ne 1 || ! $1 =~ ^[123]$ ]]; then
  echo "用法：$0 <重复编号：1、2 或 3>" >&2
  exit 2
fi

repeat="$1"
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
exec_root=${REQUIREMENTS_EXEC_ROOT:?set REQUIREMENTS_EXEC_ROOT to the prepared execution directory}
tox_runner=${REQUIREMENTS_TOX_RUNNER:?set REQUIREMENTS_TOX_RUNNER to the isolated tox executable}
db_url=${REQUIREMENTS_DB_URL:-mysql+pymysql://openstack_citest:openstack_citest@127.0.0.1:33317/}
db_container=${REQUIREMENTS_DB_CONTAINER:-marshal-cinder-mariadb-20260824}
ldap_dev_root=${REQUIREMENTS_LDAP_DEV_ROOT:-$exec_root/system-deps/libldap-dev/root}
result_root=${REQUIREMENTS_RESULT_ROOT:-$script_dir/results/requirements-formal-repetitions-2026-08-24}
repeat_dir="$result_root/repeat-$repeat"
repair_patch="$script_dir/results/requirements-cinder-active-pilot-2026-08-24/a2-maintainer.patch"

exec_root=$(realpath "$exec_root")
tox_runner=$(realpath "$tox_runner")
ldap_dev_root=$(realpath "$ldap_dev_root")
mkdir -p "$result_root"
result_root=$(realpath "$result_root")

if [[ -e $repeat_dir ]]; then
  echo "拒绝覆盖已有正式重复目录：$repeat_dir" >&2
  exit 3
fi
if [[ ! -f $ldap_dev_root/usr/include/lber.h ]]; then
  echo "缺少 Keystone 构建所需的 lber.h：$ldap_dev_root" >&2
  exit 4
fi
if [[ ! -f $repair_patch ]]; then
  echo "缺少 Cinder 维护者修复：$repair_patch" >&2
  exit 5
fi

work_root=$(mktemp -d "/tmp/marshal-requirements-formal-r${repeat}.XXXXXX")
mkdir -p "$repeat_dir/runs" "$work_root/consumers"

repos=(cinder heat ironic keystone nova placement)
configs=(a0 a1 a2 a3-before a3-after)

declare -A base_dirs=(
  [cinder]="$exec_root/cinder"
  [heat]="$exec_root/heat-base"
  [ironic]="$exec_root/ironic-base"
  [keystone]="$exec_root/keystone-base"
  [nova]="$exec_root/nova-base"
  [placement]="$exec_root/placement-base"
)
declare -A commits=(
  [cinder]=b5b763129e2bde5077c0cf3a5eb434021abaa6e0
  [heat]=79feefc60e12fab1f40e53e40318091169696a72
  [ironic]=72d6dea279cf493d855953a404868fce1b39fbf1
  [keystone]=16afc813b7e6de727d8a91e065d7824b06e32925
  [nova]=fec26fb64baef2251bf547850ae71edfa6a7413d
  [placement]=0d503c6df70aa3049c29d4c2d8672703e068463e
)
declare -A tox_envs=(
  [cinder]=py313
  [heat]=py313
  [ironic]=py313
  [keystone]=py313
  [nova]=py313
  [placement]=functional-py313
)
declare -A tests=(
  [cinder]=cinder.tests.unit.db.test_migrations.TestModelsSyncMySQL.test_models_sync
  [heat]=heat.tests.db.test_migrations.ModelsMigrationsSyncMysql.test_models_sync
  [ironic]=ironic.tests.unit.db.sqlalchemy.test_migrations.ModelsMigrationsSyncMysql.test_models_sync
  [keystone]=keystone.tests.unit.common.sql.test_upgrades.TestModelsSyncMySQL.test_models_sync
  [nova]='nova.tests.unit.db.(api|main).test_migrations.TestModelsSyncMySQL.test_models_sync'
  [placement]=placement.tests.functional.db.test_migrations.ModelsMigrationsSyncMysql.test_models_sync
)
declare -A constraint_files=(
  [a0]="$exec_root/requirements/upper-constraints.txt"
  [a1]="$exec_root/requirements-a1/upper-constraints.txt"
  [a2]="$exec_root/requirements-a1/upper-constraints.txt"
  [a3-before]="$exec_root/requirements-a3-before/upper-constraints.txt"
  [a3-after]="$exec_root/requirements-a3-after/upper-constraints.txt"
)
declare -A expected_versions=(
  [a0]=1.18.5
  [a1]=1.19.1
  [a2]=1.19.1
  [a3-before]=1.17.2
  [a3-after]=1.18.0
)

{
  printf 'repeat=%s\n' "$repeat"
  printf 'started_at=%s\n' "$(date --iso-8601=seconds)"
  printf 'work_root=%s\n' "$work_root"
  printf 'exec_root=%s\n' "$exec_root"
  printf 'tox_runner=%s\n' "$tox_runner"
  printf 'database_container=%s\n' "$db_container"
  printf 'database_url=%s\n' "$db_url"
  printf 'ldap_dev_root=%s\n' "$ldap_dev_root"
  printf 'libldap_runtime=%s\n' "$(dpkg-query -W -f='${Version}' libldap2 2>/dev/null || printf unknown)"
  printf 'platform=%s\n' "$(uname -a)"
  "$tox_runner" --version
  docker inspect --format='database_image={{.Config.Image}}' "$db_container" 2>/dev/null || true
} >"$repeat_dir/environment.txt"

printf 'repeat\tconfig\trepository\texpected_version\tactual_version\texpected_result\tstarted_at\tfinished_at\tduration_seconds\texit_code\ttest_executed\tversion_ok\tdirection_ok\n' \
  >"$repeat_dir/run-results.tsv"

preflight_failures=0
for repo in "${repos[@]}"; do
  actual_commit=$(git -C "${base_dirs[$repo]}" rev-parse HEAD)
  if [[ $actual_commit != "${commits[$repo]}" ]]; then
    printf '%s commit mismatch: %s\n' "$repo" "$actual_commit" >&2
    preflight_failures=$((preflight_failures + 1))
  fi
done
for config in "${configs[@]}"; do
  actual_version=$(sed -n 's/^alembic===//p' "${constraint_files[$config]}")
  if [[ $actual_version != "${expected_versions[$config]}" ]]; then
    printf '%s constraint version mismatch: %s\n' "$config" "$actual_version" >&2
    preflight_failures=$((preflight_failures + 1))
  fi
done
if [[ $preflight_failures -ne 0 ]]; then
  exit 6
fi

unexpected=0
for config in "${configs[@]}"; do
  constraints=${constraint_files[$config]}
  expected_version=${expected_versions[$config]}

  for repo in "${repos[@]}"; do
    consumer="$work_root/consumers/$config/$repo"
    run_dir="$repeat_dir/runs/$config/$repo"
    mkdir -p "$run_dir"
    git -c advice.detachedHead=false clone --quiet --no-hardlinks "${base_dirs[$repo]}" "$consumer"
    git -c advice.detachedHead=false -C "$consumer" checkout --detach --quiet "${commits[$repo]}"

    if [[ $config == a2 && $repo == cinder ]]; then
      git -C "$consumer" apply "$repair_patch"
    fi

    git -C "$consumer" rev-parse HEAD >"$run_dir/consumer-commit.txt"
    git -C "$consumer" status --short >"$run_dir/git-status.txt"
    git -C "$consumer" diff >"$run_dir/applied.diff"
    {
      printf 'work_dir=%s\n' "$consumer"
      printf 'git_root=%s\n' "$(git -C "$consumer" rev-parse --show-toplevel)"
      printf 'constraints=%s\n' "$constraints"
      printf 'expected_version=%s\n' "$expected_version"
      printf 'tox_env=%s\n' "${tox_envs[$repo]}"
      printf 'test=%s\n' "${tests[$repo]}"
    } >"$run_dir/context.txt"

    expected_result=pass
    if [[ $config == a1 && $repo == cinder ]]; then
      expected_result=fail_remove_constraint
    fi
    {
      printf 'timeout --signal=TERM 20m env OS_TEST_DBAPI_ADMIN_CONNECTION=%q TOX_CONSTRAINTS_FILE=%q' "$db_url" "$constraints"
      if [[ $repo == keystone ]]; then
        printf ' CFLAGS=%q LDFLAGS=%q' "-I$ldap_dev_root/usr/include" "-L$ldap_dev_root/usr/lib/x86_64-linux-gnu"
      fi
      printf ' %q -r -x %q -e %q -- %q\n' "$tox_runner" \
        'testenv.pass_env=OS_TEST_DBAPI_ADMIN_CONNECTION,CFLAGS,LDFLAGS' \
        "${tox_envs[$repo]}" "${tests[$repo]}"
    } >"$run_dir/command.txt"

    started_at=$(date --iso-8601=seconds)
    started_epoch=$(date +%s)
    (
      cd "$consumer" || exit 125
      export OS_TEST_DBAPI_ADMIN_CONNECTION="$db_url"
      export TOX_CONSTRAINTS_FILE="$constraints"
      if [[ $repo == keystone ]]; then
        export CFLAGS="-I$ldap_dev_root/usr/include"
        export LDFLAGS="-L$ldap_dev_root/usr/lib/x86_64-linux-gnu"
      fi
      /usr/bin/time -v -o "$run_dir/time.txt" \
        timeout --signal=TERM 20m "$tox_runner" -r \
        -x 'testenv.pass_env=OS_TEST_DBAPI_ADMIN_CONNECTION,CFLAGS,LDFLAGS' \
        -e "${tox_envs[$repo]}" -- "${tests[$repo]}" \
        >"$run_dir/tox.log" 2>&1
    )
    exit_code=$?
    finished_epoch=$(date +%s)
    finished_at=$(date --iso-8601=seconds)
    duration_seconds=$((finished_epoch - started_epoch))
    printf '%s\n' "$exit_code" >"$run_dir/exit-code.txt"

    env_python="$consumer/.tox/${tox_envs[$repo]}/bin/python"
    if [[ -x $env_python ]]; then
      "$env_python" - <<'PY' >"$run_dir/versions.txt" 2>"$run_dir/version-error.txt"
import alembic
import sqlalchemy
import sys

print(f"python={sys.version.split()[0]}")
print(f"alembic={alembic.__version__}")
print(f"sqlalchemy={sqlalchemy.__version__}")
PY
    fi
    actual_version=missing
    if [[ -f $run_dir/versions.txt ]]; then
      actual_version=$(sed -n 's/^alembic=//p' "$run_dir/versions.txt")
    fi

    test_executed=false
    if rg -q 'test_models_sync .*\.\.\. (ok|FAILED)' "$run_dir/tox.log"; then
      test_executed=true
    fi
    version_ok=false
    if [[ $actual_version == "$expected_version" ]]; then
      version_ok=true
    fi
    direction_ok=false
    if [[ $expected_result == pass && $exit_code -eq 0 && $test_executed == true ]]; then
      direction_ok=true
    elif [[ $expected_result == fail_remove_constraint && $exit_code -ne 0 && $test_executed == true ]] \
      && rg -q 'remove_constraint' "$run_dir/tox.log"; then
      direction_ok=true
    fi
    if [[ $version_ok != true || $direction_ok != true ]]; then
      unexpected=$((unexpected + 1))
    fi

    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$repeat" "$config" "$repo" "$expected_version" "$actual_version" \
      "$expected_result" "$started_at" "$finished_at" "$duration_seconds" \
      "$exit_code" "$test_executed" "$version_ok" "$direction_ok" \
      >>"$repeat_dir/run-results.tsv"
    printf '%s %s: exit=%s version=%s direction_ok=%s\n' \
      "$config" "$repo" "$exit_code" "$actual_version" "$direction_ok"
  done
done

{
  printf 'finished_at=%s\n' "$(date --iso-8601=seconds)"
  printf 'unexpected_results=%s\n' "$unexpected"
} >>"$repeat_dir/environment.txt"

exit "$unexpected"
