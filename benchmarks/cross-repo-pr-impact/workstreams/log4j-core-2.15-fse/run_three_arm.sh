#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"
WORK_ROOT="${REPO_ROOT}/.work/log4j-core-2.15-fse"
MIRROR="${WORK_ROOT}/repositories/gdv-xport.git"
RUN_ROOT="${WORK_ROOT}/runs"
M2_ROOT="${WORK_ROOT}/m2"
RESULT_ROOT="${REPO_ROOT}/benchmarks/cross-repo-pr-impact/results/log4j-core-2.15-fse-replay-2026-08-25"
JAVA_HOME="/usr/lib/jvm/java-11-openjdk-amd64"
PATH="${JAVA_HOME}/bin:/home/zhihao/.local/maven/bin:/usr/bin:/bin"
export JAVA_HOME PATH

mkdir -p "${WORK_ROOT}/repositories" "${RUN_ROOT}" "${M2_ROOT}" "${RESULT_ROOT}"

if [[ ! -d "${MIRROR}" ]]; then
  git clone --mirror https://github.com/oboehm/gdv.xport.git "${MIRROR}"
  git --git-dir="${MIRROR}" fetch origin '+refs/pull/*/head:refs/pull/*/head'
fi

prepare_arm() {
  local arm="$1"
  local revision="$2"
  local arm_dir="${RUN_ROOT}/${arm}"

  if [[ ! -d "${arm_dir}/.git" ]]; then
    git clone --shared "${MIRROR}" "${arm_dir}"
  fi
  git -C "${arm_dir}" checkout --detach --force "${revision}"
}

run_arm() {
  local arm="$1"
  local arm_dir="${RUN_ROOT}/${arm}"
  local tmp_dir="${WORK_ROOT}/tmp/${arm}"
  mkdir -p "${tmp_dir}"

  env \
    TMPDIR="${tmp_dir}" \
    MAVEN_OPTS="-Djava.io.tmpdir=${tmp_dir}" \
    mvn -B -ntp \
      -Dmaven.repo.local="${M2_ROOT}/${arm}" \
      -Djava.io.tmpdir="${tmp_dir}" \
      -pl lib -am clean test \
      -l "${RESULT_ROOT}/${arm}.log" \
      -f "${arm_dir}/pom.xml"
}

prepare_arm a0 3f806a2a37029b6d2a0afbc716917dacc19bea17
prepare_arm a1 3bf9996a0afdbf426e920e03aafe069cab4e2491
prepare_arm a2-isolated 3bf9996a0afdbf426e920e03aafe069cab4e2491
git -C "${RUN_ROOT}/a2-isolated" apply "${SCRIPT_DIR}/gdv-maintainer-api-sync.patch"

run_arm a0
a0_exit=$?
run_arm a1
a1_exit=$?
run_arm a2-isolated
a2_exit=$?

printf 'a0=%s a1=%s a2=%s\n' "${a0_exit}" "${a1_exit}" "${a2_exit}"
[[ "${a0_exit}" -eq 0 && "${a1_exit}" -ne 0 && "${a2_exit}" -eq 0 ]]
