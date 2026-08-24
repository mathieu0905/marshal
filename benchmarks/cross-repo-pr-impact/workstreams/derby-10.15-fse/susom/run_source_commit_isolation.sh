#!/usr/bin/env bash

set -euo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
benchmark_root=$(cd "$script_dir/../../.." && pwd)
result_dir=${RESULT_DIR:-"$benchmark_root/results/derby-10.15-fse-susom-source-isolation-2026-08-25"}
derby_repository=${DERBY_SOURCE_REPOSITORY:-https://github.com/apache/derby.git}
target_repository=${DERBY_TARGET_REPOSITORY:-https://github.com/susom/database.git}
source_parent=8f3b7b2fa2f3e775dc90fb3cfa9f46257ae8df0e
source_child=5a6efccce73b05ac7a27512563868192303f564d
target_commit=b9aac59d053af41144f59c77a7f9053f8fe61102
exact_version=10.15.0.0-exact
test_selector=com.github.susom.database.test.VertxLoggingTest#testMdcTransferToWorkerDatabase
source_java_home=${DERBY_SOURCE_JAVA_HOME:?Set DERBY_SOURCE_JAVA_HOME to a JDK 9 installation}
source_ant_home=${DERBY_SOURCE_ANT_HOME:?Set DERBY_SOURCE_ANT_HOME to an Ant installation}
source_junit=${DERBY_SOURCE_JUNIT:?Set DERBY_SOURCE_JUNIT to JUnit 3.8.2}
target_java_home=${DERBY_TARGET_JAVA_HOME:-/home/zhihao/.jdks/jdk-11.0.30+7}
m2_seed=${DERBY_M2_SEED:-$HOME/.m2/repository}

if [[ -e $result_dir ]]; then
  echo "拒绝覆盖已有 Derby 源提交隔离目录：$result_dir" >&2
  exit 3
fi
for path in "$source_java_home/bin/java" "$source_ant_home/bin/ant" "$source_junit" \
  "$target_java_home/bin/java" "$m2_seed"; do
  if [[ ! -e $path ]]; then
    echo "缺少重放输入：$path" >&2
    exit 4
  fi
done

work_root=$(mktemp -d /tmp/derby-source-commit-replay.XXXXXX)
mkdir -p "$result_dir/source-builds/toolchain-attempts" "$result_dir/artifacts" \
  "$result_dir/target-arms" "$work_root/m2/parent" "$work_root/m2/child"
git clone --mirror --quiet "$derby_repository" "$work_root/derby.git"
git clone --mirror --quiet "$target_repository" "$work_root/target.git"
git --git-dir="$work_root/derby.git" cat-file -e "$source_parent^{commit}"
git --git-dir="$work_root/derby.git" cat-file -e "$source_child^{commit}"
actual_parent=$(git --git-dir="$work_root/derby.git" rev-parse "$source_child^")
if [[ $actual_parent != "$source_parent" ]]; then
  echo "源提交父子关系不匹配：$actual_parent" >&2
  exit 5
fi
git --git-dir="$work_root/target.git" cat-file -e "$target_commit^{commit}"
git --git-dir="$work_root/derby.git" diff "$source_parent" "$source_child" \
  >"$result_dir/source-parent-child.patch"

cp -a --reflink=auto "$m2_seed/." "$work_root/m2/parent/"
cp -a --reflink=auto "$m2_seed/." "$work_root/m2/child/"

{
  printf 'started_at=%s\n' "$(date --iso-8601=seconds)"
  printf 'work_root=%s\n' "$work_root"
  printf 'derby_repository=%s\n' "$derby_repository"
  printf 'source_parent=%s\n' "$source_parent"
  printf 'source_child=%s\n' "$source_child"
  printf 'target_repository=%s\n' "$target_repository"
  printf 'target_commit=%s\n' "$target_commit"
  printf 'exact_test_version=%s\n' "$exact_version"
  printf 'source_java_home=%s\n' "$source_java_home"
  "$source_java_home/bin/java" -version 2>&1
  printf 'source_ant_home=%s\n' "$source_ant_home"
  JAVA_HOME="$source_java_home" "$source_ant_home/bin/ant" -version
  printf 'source_junit=%s\n' "$source_junit"
  printf 'source_build_command=ant -quiet -Djunit=<JUnit-3.8.2> clobber buildsource buildjars\n'
  printf 'target_java_home=%s\n' "$target_java_home"
  JAVA_HOME="$target_java_home" PATH="$target_java_home/bin:$PATH" java -version 2>&1
  JAVA_HOME="$target_java_home" PATH="$target_java_home/bin:$PATH" mvn -version
} >"$result_dir/environment.txt"

git clone --quiet "$work_root/derby.git" "$work_root/missing-junit"
git -c advice.detachedHead=false -C "$work_root/missing-junit" checkout --detach --quiet "$source_parent"
set +e
(
  cd "$work_root/missing-junit" || exit 125
  JAVA_HOME="$source_java_home" ANT_HOME="$source_ant_home" \
    PATH="$source_java_home/bin:$source_ant_home/bin:/usr/bin:/bin" \
    "$source_ant_home/bin/ant" -quiet clobber buildsource buildjars
) >"$result_dir/source-builds/toolchain-attempts/missing-junit.log" 2>&1
missing_junit_status=$?
set -e
printf '%s\n' "$missing_junit_status" \
  >"$result_dir/source-builds/toolchain-attempts/missing-junit-exit-code.txt"

printf 'side\tcommit\texit_code\tderby_bytes\tderbyshared_bytes\tderbytools_bytes\n' \
  >"$result_dir/source-build-results.tsv"
for side in parent child; do
  commit=$source_parent
  if [[ $side == child ]]; then
    commit=$source_child
  fi
  source_tree="$work_root/source-$side"
  source_output="$result_dir/source-builds/$side"
  artifact_output="$result_dir/artifacts/$side"
  mkdir -p "$source_output" "$artifact_output"
  git clone --quiet "$work_root/derby.git" "$source_tree"
  git -c advice.detachedHead=false -C "$source_tree" checkout --detach --quiet "$commit"
  printf 'ant -quiet -Djunit=%q clobber buildsource buildjars\n' "$source_junit" \
    >"$source_output/build-command.txt"
  set +e
  (
    cd "$source_tree" || exit 125
    JAVA_HOME="$source_java_home" ANT_HOME="$source_ant_home" \
      PATH="$source_java_home/bin:$source_ant_home/bin:/usr/bin:/bin" \
      "$source_ant_home/bin/ant" -quiet "-Djunit=$source_junit" clobber buildsource buildjars
  ) >"$source_output/build.log" 2>&1
  build_status=$?
  set -e
  printf '%s\n' "$build_status" >"$source_output/exit-code.txt"
  if [[ $build_status -ne 0 ]]; then
    exit "$build_status"
  fi
  for jar_name in derby.jar derbyshared.jar derbytools.jar; do
    cp "$source_tree/jars/sane/$jar_name" "$artifact_output/$jar_name"
  done
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$side" "$commit" "$build_status" \
    "$(stat -c %s "$artifact_output/derby.jar")" \
    "$(stat -c %s "$artifact_output/derbyshared.jar")" \
    "$(stat -c %s "$artifact_output/derbytools.jar")" \
    >>"$result_dir/source-build-results.tsv"
done

printf 'side\tartifact\tembedded_driver\n' >"$result_dir/jar-inventory.tsv"
for side in parent child; do
  for artifact in derby derbyshared derbytools; do
    presence=absent
    if unzip -Z1 "$result_dir/artifacts/$side/$artifact.jar" | \
      awk '$0 == "org/apache/derby/jdbc/EmbeddedDriver.class" { found=1 } END { exit !found }'; then
      presence=present
    fi
    printf '%s\t%s\t%s\n' "$side" "$artifact" "$presence" \
      >>"$result_dir/jar-inventory.tsv"
  done
done
awk -F '\t' '
  $1 == "parent" && $2 == "derby" && $3 == "present" { parent_derby=1 }
  $1 == "child" && $2 == "derby" && $3 == "absent" { child_derby=1 }
  $1 == "child" && $2 == "derbytools" && $3 == "present" { child_tools=1 }
  END { exit !(parent_derby && child_derby && child_tools) }
' "$result_dir/jar-inventory.tsv"

for side in parent child; do
  local_repo="$work_root/m2/$side"
  artifact_dir="$result_dir/artifacts/$side"
  for artifact in derbyshared derby derbytools; do
    JAVA_HOME="$target_java_home" PATH="$target_java_home/bin:$PATH" \
      mvn -q "-Dmaven.repo.local=$local_repo" install:install-file \
      "-Dfile=$artifact_dir/$artifact.jar" "-DpomFile=$script_dir/poms/$artifact.pom" \
      >"$result_dir/source-builds/$side/install-$artifact.log" 2>&1
  done
done

printf 'arm\tsource_side\texit_code\ttests\tfailures\terrors\tdirection\tduration_seconds\n' \
  >"$result_dir/target-run-results.tsv"
unexpected=0
for arm in parent child child_repaired; do
  side=$arm
  expected=pass
  if [[ $arm == child_repaired ]]; then
    side=child
  elif [[ $arm == child ]]; then
    expected=fail
  fi
  target_tree="$work_root/target-$arm"
  arm_output="$result_dir/target-arms/$arm"
  local_repo="$work_root/m2/$side"
  mkdir -p "$arm_output"
  git clone --quiet "$work_root/target.git" "$target_tree"
  git -c advice.detachedHead=false -C "$target_tree" checkout --detach --quiet "$target_commit"
  JAVA_HOME="$target_java_home" PATH="$target_java_home/bin:$PATH" \
    mvn -q -f "$target_tree/pom.xml" "-Dmaven.repo.local=$local_repo" \
    org.codehaus.mojo:versions-maven-plugin:2.16.2:use-dep-version \
    -Dincludes=org.apache.derby:derby "-DdepVersion=$exact_version" \
    -DforceVersion=true -DgenerateBackupPoms=false
  if [[ $arm == child_repaired ]]; then
    git -C "$target_tree" apply "$script_dir/susom-source-exact-repair.patch"
  fi
  git -C "$target_tree" diff -- pom.xml >"$arm_output/input.patch"
  printf 'mvn -Dfindbugs.skip=true -Dtest=%s -DfailIfNoTests=false test\n' \
    "$test_selector" >"$arm_output/test-command.txt"
  started_epoch=$(date +%s)
  set +e
  JAVA_HOME="$target_java_home" PATH="$target_java_home/bin:$PATH" \
    mvn -f "$target_tree/pom.xml" "-Dmaven.repo.local=$local_repo" \
    -Dfindbugs.skip=true "-Dtest=$test_selector" -DfailIfNoTests=false test \
    >"$arm_output/maven-test.log" 2>&1
  test_status=$?
  set -e
  duration_seconds=$(($(date +%s) - started_epoch))
  printf '%s\n' "$test_status" >"$arm_output/exit-code.txt"
  JAVA_HOME="$target_java_home" PATH="$target_java_home/bin:$PATH" \
    mvn -q -f "$target_tree/pom.xml" "-Dmaven.repo.local=$local_repo" dependency:tree \
    -Dincludes=org.apache.derby -DoutputFile="$arm_output/derby-dependency-tree.txt" \
    -DappendOutput=false >"$arm_output/dependency-tree-command.log" 2>&1
  if [[ -d $target_tree/target/surefire-reports ]]; then
    cp -a "$target_tree/target/surefire-reports/." "$arm_output/"
  fi
  report="$target_tree/target/surefire-reports/TEST-com.github.susom.database.test.VertxLoggingTest.xml"
  tests=0
  failures=0
  errors=0
  if [[ -f $report ]]; then
    tests=$(xmllint --xpath 'string(/testsuite/@tests)' "$report")
    failures=$(xmllint --xpath 'string(/testsuite/@failures)' "$report")
    errors=$(xmllint --xpath 'string(/testsuite/@errors)' "$report")
  fi
  direction=unexpected
  if [[ $expected == pass && $test_status -eq 0 && $tests -eq 1 && $failures -eq 0 && $errors -eq 0 ]]; then
    direction=pass
  elif [[ $expected == fail && $test_status -ne 0 && $tests -eq 1 && $errors -eq 1 ]] && \
    grep -Fq 'Failed to load driver class org.apache.derby.jdbc.EmbeddedDriver' "$arm_output/maven-test.log"; then
    direction=expected_embedded_driver_failure
  else
    unexpected=$((unexpected + 1))
  fi
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$arm" "$side" "$test_status" \
    "$tests" "$failures" "$errors" "$direction" "$duration_seconds" \
    >>"$result_dir/target-run-results.tsv"
done

{
  printf 'finished_at=%s\n' "$(date --iso-8601=seconds)"
  printf 'missing_junit_attempt_exit_code=%s\n' "$missing_junit_status"
  printf 'unexpected_results=%s\n' "$unexpected"
} >>"$result_dir/environment.txt"

exit "$unexpected"
