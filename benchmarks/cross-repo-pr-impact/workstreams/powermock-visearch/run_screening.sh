#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "用法：$0 <结果目录>" >&2
  exit 2
fi

output_dir=$(realpath -m "$1")
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(git -C "$script_dir" rev-parse --show-toplevel)
task_root=${MARSHAL_TASK_TMP:-$repo_root/.work/powermock-visearch}
repo_dir=$task_root/client
cache_dir=$task_root/m2
java_home=${JAVA8_HOME:-/home/zhihao/.jdks/jdk8u482-b08}
target_commit=5f6e72ec5d16987f4cee959ef2063a20989cb40f
repair_commit=8fdd4826f7719be850614fc5359bdf4cca32a20c
artifact_dir=$cache_dir/org/powermock/powermock-api/1.6.4
artifact_jar=$artifact_dir/powermock-api-1.6.4.jar
artifact_pom=$artifact_dir/powermock-api-1.6.4.pom

if [[ ! -x $java_home/bin/java || ! -x $java_home/bin/jar ]]; then
  echo "找不到可用的 Java 8：$java_home" >&2
  exit 2
fi

mkdir -p "$output_dir" "$task_root" "$cache_dir" "$task_root/tmp" "$task_root/java-tmp"
export TMPDIR="$task_root/tmp"
export MAVEN_OPTS="${MAVEN_OPTS:-} -Djava.io.tmpdir=$task_root/java-tmp"

if [[ ! -d $repo_dir/.git ]]; then
  git clone --filter=blob:none --no-checkout \
    https://github.com/visenze/visearch-sdk-java.git "$repo_dir"
fi

for commit in "$target_commit" "$repair_commit"; do
  if ! git -C "$repo_dir" cat-file -e "$commit^{commit}" 2>/dev/null; then
    git -C "$repo_dir" fetch origin "$commit"
  fi
done

run_root=$(mktemp -d "$task_root/run.XXXXXX")

cleanup() {
  rm -rf -- "$run_root"
}
trap cleanup EXIT

git -C "$repo_dir" show --format=fuller --stat "$target_commit" \
  >"$output_dir/target-baseline-commit.txt"
git -C "$repo_dir" show --format=fuller --stat "$repair_commit" \
  >"$output_dir/maintainer-repair-commit.txt"
git -C "$repo_dir" show --format= "$repair_commit" -- pom.xml \
  >"$output_dir/maintainer-repair-original.diff"
"$java_home/bin/java" -version >"$output_dir/java-version.txt" 2>&1
JAVA_HOME=$java_home PATH=$java_home/bin:$PATH \
  mvn -version >"$output_dir/maven-version.txt" 2>&1

extract_arm() {
  local arm_dir=$1
  mkdir -p "$arm_dir"
  git -C "$repo_dir" archive "$target_commit" | tar -x -C "$arm_dir"
}

run_test() {
  local arm_dir=$1
  local log=$2
  set +e
  (
    cd "$arm_dir"
    JAVA_HOME=$java_home PATH=$java_home/bin:$PATH \
      mvn -B -Dmaven.repo.local="$cache_dir" test
  ) >"$log" 2>&1
  local status=$?
  set -e
  printf '%s\n' "$status"
}

run_tree() {
  local arm_dir=$1
  local log=$2
  (
    cd "$arm_dir"
    JAVA_HOME=$java_home PATH=$java_home/bin:$PATH \
      mvn -B -Dmaven.repo.local="$cache_dir" \
      org.apache.maven.plugins:maven-dependency-plugin:3.6.1:tree \
      -Dincludes=org.powermock
  ) >"$log" 2>&1
}

# 精确历史 POM 声明的是一个不存在的 JAR。先移除隔离缓存中的恢复物，
# 记录干净解析结果；该诊断不计作三臂中的测试失败。
mkdir -p "$artifact_dir"
rm -f -- "$artifact_jar"
extract_arm "$run_root/a0-clean"
clean_status=$(run_test "$run_root/a0-clean" "$output_dir/a0-clean-resolution.log")
printf '%s\n' "$clean_status" >"$output_dir/a0-clean-resolution-exit-status.txt"

curl -sS -o /dev/null \
  -w 'powermock-api-1.6.4.jar http_status=%{http_code} size=%{size_download}\n' \
  https://repo.maven.apache.org/maven2/org/powermock/powermock-api/1.6.4/powermock-api-1.6.4.jar \
  >"$output_dir/artifact-availability.txt"
curl -fsSL \
  https://repo.maven.apache.org/maven2/org/powermock/powermock-api/1.6.4/powermock-api-1.6.4.pom \
  -o "$artifact_pom"

# 公开执行记录能够越过上述历史依赖解析问题，但未提供其本地仓库。
# powermock-api 是无源码的聚合 POM；放入空 JAR 只恢复解析前提，三臂共用，
# 用于核对公开失败签名和维护者补丁是否恢复，不把它当作正式 A0 证据。
mkdir -p "$run_root/empty-artifact"
"$java_home/bin/jar" cf "$artifact_jar" -C "$run_root/empty-artifact" .
"$java_home/bin/jar" tf "$artifact_jar" \
  >"$output_dir/reconstructed-artifact-contents.txt"

extract_arm "$run_root/a0"
cp "$run_root/a0/pom.xml" "$output_dir/a0-pom.xml"
a0_status=$(run_test "$run_root/a0" "$output_dir/a0-test.log")
printf '%s\n' "$a0_status" >"$output_dir/a0-exit-status.txt"
run_tree "$run_root/a0" "$output_dir/a0-dependency-tree.log"

extract_arm "$run_root/a1"
sed -i \
  '/<artifactId>powermock-module-junit4<\/artifactId>/{n;s/1\.6\.4/1.6.5/;}' \
  "$run_root/a1/pom.xml"
cp "$run_root/a1/pom.xml" "$output_dir/a1-pom.xml"
a1_status=$(run_test "$run_root/a1" "$output_dir/a1-test.log")
printf '%s\n' "$a1_status" >"$output_dir/a1-exit-status.txt"
run_tree "$run_root/a1" "$output_dir/a1-dependency-tree.log"

extract_arm "$run_root/a2"
sed -i \
  '/<artifactId>powermock-module-junit4<\/artifactId>/{n;s/1\.6\.4/1.6.5/;}' \
  "$run_root/a2/pom.xml"
git -C "$run_root/a2" apply "$script_dir/maintainer-repair.patch"
cp "$run_root/a2/pom.xml" "$output_dir/a2-pom.xml"
a2_status=$(run_test "$run_root/a2" "$output_dir/a2-test.log")
printf '%s\n' "$a2_status" >"$output_dir/a2-exit-status.txt"
run_tree "$run_root/a2" "$output_dir/a2-dependency-tree.log"

set +e
/usr/bin/diff -u --label a0/pom.xml --label a1/pom.xml \
  "$run_root/a0/pom.xml" "$run_root/a1/pom.xml" \
  >"$output_dir/a0-to-a1.diff"
/usr/bin/diff -u --label a1/pom.xml --label a2/pom.xml \
  "$run_root/a1/pom.xml" "$run_root/a2/pom.xml" \
  >"$output_dir/a1-to-a2.diff"
set -e

jq -n \
  --argjson clean_status "$clean_status" \
  --argjson a0_status "$a0_status" \
  --argjson a1_status "$a1_status" \
  --argjson a2_status "$a2_status" \
  '{
    screened_at: "2026-08-24",
    candidate_id: "fse2024-behavioral-0615",
    native_command: "Java 8 mvn test",
    source_change: {
      repository: "powermock/powermock",
      package: "org.powermock:powermock-module-junit4",
      before: "1.6.4",
      after: "1.6.5",
      release_commit: "f075346a5524e68b33ad6f2346fd5ed2111d7ad0"
    },
    target: {
      repository: "visenze/visearch-sdk-java",
      baseline_commit: "5f6e72ec5d16987f4cee959ef2063a20989cb40f",
      repair_commit: "8fdd4826f7719be850614fc5359bdf4cca32a20c"
    },
    clean_baseline: {
      exit_status: $clean_status,
      result: "dependency_resolution_failed",
      missing_artifact: "org.powermock:powermock-api:jar:1.6.4"
    },
    reconstructed_arms: [
      {
        arm: "A0",
        module_junit4: "1.6.4",
        api_mockito: "1.6.4",
        exit_status: $a0_status,
        result: "tests_passed",
        tests_run: 71
      },
      {
        arm: "A1",
        module_junit4: "1.6.5",
        api_mockito: "1.6.4",
        exit_status: $a1_status,
        result: "tests_failed",
        failure: "MockingFrameworkReporterFactoryImpl could not be located in classpath"
      },
      {
        arm: "A2",
        module_junit4: "1.6.5",
        api_mockito: "1.6.4",
        maintainer_change: "delete explicit org.powermock:powermock-api:1.6.4",
        exit_status: $a2_status,
        result: "same_failure_as_a1",
        failure: "MockingFrameworkReporterFactoryImpl could not be located in classpath"
      }
    ],
    decision: "rejected_no_strict_three_arm_and_maintainer_change_does_not_restore",
    strict_three_arm_established: false,
    accepted_causal_cases: 0,
    bounded_negative_labels: 0,
    a3_cases: 0,
    sibling_records_label: "unknown_without_independent_maintainer_repair",
    sibling_candidate_ids: [
      "fse2024-behavioral-0611",
      "fse2024-behavioral-0612",
      "fse2024-behavioral-0613",
      "fse2024-behavioral-0614",
      "fse2024-behavioral-0616",
      "fse2024-behavioral-0617",
      "fse2024-behavioral-0618"
    ]
  }' >"$output_dir/summary.json"

jq -e '
  .clean_baseline.exit_status != 0 and
  .reconstructed_arms[0].exit_status == 0 and
  .reconstructed_arms[1].exit_status != 0 and
  .reconstructed_arms[2].exit_status != 0 and
  .accepted_causal_cases == 0 and
  .bounded_negative_labels == 0 and
  .a3_cases == 0
' "$output_dir/summary.json" >/dev/null
grep -F 'org.powermock:powermock-api:jar:1.6.4' \
  "$output_dir/a0-clean-resolution.log" >/dev/null
grep -F '[INFO] BUILD FAILURE' "$output_dir/a0-clean-resolution.log" >/dev/null
grep -F 'MockingFrameworkReporterFactoryImpl could not be located in classpath' \
  "$output_dir/a1-test.log" >/dev/null
grep -F 'MockingFrameworkReporterFactoryImpl could not be located in classpath' \
  "$output_dir/a2-test.log" >/dev/null

echo "筛选完成：公开失败已复现，但维护者提交不能恢复；正式接纳零条。"
