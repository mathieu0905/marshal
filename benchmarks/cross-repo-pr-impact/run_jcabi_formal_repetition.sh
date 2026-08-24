#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 1 || ! $1 =~ ^[123]$ ]]; then
  echo "用法：$0 <重复编号：1、2 或 3>" >&2
  exit 2
fi

repeat="$1"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
result_root="${script_dir}/results/jcabi-formal-repetitions-2026-08-24"
repeat_dir="${result_root}/repeat-${repeat}"
input_dir="${result_root}/inputs"
repair_dir="${script_dir}/results"

if [[ -e "${repeat_dir}" ]]; then
  echo "拒绝覆盖已有正式重复目录：${repeat_dir}" >&2
  exit 3
fi

jcabi_user_home="$(getent passwd "$(id -u)" | cut -d: -f6)"
jcabi_m2_seed="${JCABI_M2_SEED:-${jcabi_user_home}/.m2/repository}"
if [[ ! -d "${jcabi_m2_seed}" ]]; then
  echo "依赖种子目录不存在：${jcabi_m2_seed}" >&2
  exit 4
fi

export JAVA_HOME="/usr/lib/jvm/java-11-openjdk-amd64"
export PATH="${JAVA_HOME}/bin:${PATH}"

work_root="$(mktemp -d "/tmp/marshal-jcabi-formal-r${repeat}.XXXXXX")"
mkdir -p "${repeat_dir}/runs" "${work_root}/mirrors" \
  "${work_root}/consumers" "${work_root}/m2"

declare -A remote=(
  [jcabi-s3]="https://github.com/jcabi/jcabi-s3.git"
  [jcabi-simpledb]="https://github.com/jcabi/jcabi-simpledb.git"
  [jcabi-w3c]="https://github.com/jcabi/jcabi-w3c.git"
  [jcabi-maven-plugin]="https://github.com/jcabi/jcabi-maven-plugin.git"
)
declare -A commit=(
  [jcabi-s3]="0efa37ae2c431ae148e921dc3c1a9fcb8aa2bd3a"
  [jcabi-simpledb]="4af3ea931691caa0a667852b626485b1b0cbffcf"
  [jcabi-w3c]="4054d4ad3c26607ec1bd8221b2bb1faa70ee78b0"
  [jcabi-maven-plugin]="c6d7c3d883b5176a0532516af477f77f96884ebb"
)

repos=(jcabi-s3 jcabi-simpledb jcabi-w3c jcabi-maven-plugin)
configs=(a0 a1 a2 a3-before a3-after)

{
  echo "repeat=${repeat}"
  echo "started_at=$(date --iso-8601=seconds)"
  echo "work_root=${work_root}"
  echo "dependency_seed=${jcabi_m2_seed}"
  java -version 2>&1
  mvn -version
  uname -a
} > "${repeat_dir}/environment.txt"

printf 'repeat\tconfig\trepository\texpected_version\tstarted_at\tfinished_at\tduration_seconds\texit_code\tversion_artifact_found\n' \
  > "${repeat_dir}/run-results.tsv"

for repo in "${repos[@]}"; do
  git clone --mirror --quiet "${remote[$repo]}" "${work_root}/mirrors/${repo}.git"
  git --git-dir="${work_root}/mirrors/${repo}.git" cat-file -e "${commit[$repo]}^{commit}"
done

for config in "${configs[@]}"; do
  case "${config}" in
    a0) version="0.24.1" ;;
    a1|a2) version="0.25.1" ;;
    a3-before) version="0.22.2" ;;
    a3-after) version="0.22.3" ;;
  esac

  m2_dir="${work_root}/m2/${config}"
  mkdir -p "${m2_dir}"
  cp -a "${jcabi_m2_seed}/." "${m2_dir}/"

  for repo in "${repos[@]}"; do
    consumer="${work_root}/consumers/${config}/${repo}"
    run_dir="${repeat_dir}/runs/${config}/${repo}"
    mkdir -p "${run_dir}/reports"
    git clone --quiet "${work_root}/mirrors/${repo}.git" "${consumer}"
    git -C "${consumer}" checkout --detach --quiet "${commit[$repo]}"

    if [[ "${config}" != "a0" ]]; then
      git -C "${consumer}" apply \
        "${input_dir}/${repo}-to-${version}.patch"
    fi
    if [[ "${config}" == "a2" && "${repo}" == "jcabi-s3" ]]; then
      git -C "${consumer}" apply \
        "${repair_dir}/jcabi-s3-tv-removal-target-repair.patch"
    fi
    if [[ "${config}" == "a2" && "${repo}" == "jcabi-simpledb" ]]; then
      git -C "${consumer}" apply \
        "${repair_dir}/jcabi-simpledb-tv-removal-target-repair.patch"
    fi

    git -C "${consumer}" rev-parse HEAD > "${run_dir}/consumer-commit.txt"
    git -C "${consumer}" status --short > "${run_dir}/git-status.txt"
    git -C "${consumer}" diff > "${run_dir}/applied.diff"

    if [[ "${repo}" == "jcabi-maven-plugin" ]]; then
      goals=(clean verify -B)
    else
      goals=(clean test -B)
    fi
    printf 'timeout --signal=TERM 45m mvn -Dmaven.repo.local=%q' "${m2_dir}" \
      > "${run_dir}/command.txt"
    printf ' %q' "${goals[@]}" >> "${run_dir}/command.txt"
    printf '\n' >> "${run_dir}/command.txt"

    started_at="$(date --iso-8601=seconds)"
    started_epoch="$(date +%s)"
    set +e
    (
      cd "${consumer}"
      timeout --signal=TERM 45m mvn \
        "-Dmaven.repo.local=${m2_dir}" "${goals[@]}"
    ) > "${run_dir}/maven.log" 2>&1
    exit_code="$?"
    set -e
    finished_epoch="$(date +%s)"
    finished_at="$(date --iso-8601=seconds)"
    duration_seconds="$((finished_epoch - started_epoch))"
    printf '%s\n' "${exit_code}" > "${run_dir}/exit-code.txt"

    (
      cd "${consumer}"
      find target -type f \
        \( -path '*/surefire-reports/*' \
        -o -path '*/invoker-reports/*' \
        -o -path '*/it/*/build.log' \) \
        -exec cp --parents {} "${run_dir}/reports" \; 2>/dev/null || true
    )

    {
      echo "expected_version=${version}"
      echo "declared_locations:"
      rg -n -A 2 '<artifactId>jcabi-aspects</artifactId>' \
        "${consumer}/pom.xml" "${consumer}/src/it" -g 'pom.xml' 2>/dev/null || true
      echo "resolved_artifacts:"
      find "${m2_dir}" "${consumer}/target" -type f \
        -path "*/com/jcabi/jcabi-aspects/${version}/jcabi-aspects-${version}.jar" \
        -print 2>/dev/null || true
    } > "${run_dir}/version-evidence.txt"
    if rg -q '/jcabi-aspects-[^/]+\.jar$' "${run_dir}/version-evidence.txt"; then
      artifact_found="true"
    else
      artifact_found="false"
    fi

    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "${repeat}" "${config}" "${repo}" "${version}" \
      "${started_at}" "${finished_at}" "${duration_seconds}" \
      "${exit_code}" "${artifact_found}" \
      >> "${repeat_dir}/run-results.tsv"
  done
done

echo "finished_at=$(date --iso-8601=seconds)" >> "${repeat_dir}/environment.txt"
echo "正式重复 ${repeat} 已完成；结果：${repeat_dir}"
echo "临时运行根目录：${work_root}"
