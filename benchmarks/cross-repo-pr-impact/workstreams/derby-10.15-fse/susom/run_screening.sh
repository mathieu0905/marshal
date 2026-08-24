#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
BENCHMARK_ROOT=$(cd "$SCRIPT_DIR/../../.." && pwd)
RESULT_DIR=${RESULT_DIR:-"$BENCHMARK_ROOT/results/derby-10.15-fse-susom-2026-08-25"}
JAVA_HOME=${JAVA_HOME:-/home/zhihao/.jdks/jdk-11.0.30+7}
JAVA8_HOME=${JAVA8_HOME:-/home/zhihao/.jdks/jdk8u482-b08}
MAVEN_REPO=${MAVEN_REPO:-"$HOME/.m2/repository"}
TARGET_REPOSITORY=${TARGET_REPOSITORY:-https://github.com/susom/database.git}
TARGET_COMMIT=b9aac59d053af41144f59c77a7f9053f8fe61102
TEST_SELECTOR=com.github.susom.database.test.VertxLoggingTest#testMdcTransferToWorkerDatabase

export JAVA_HOME
export PATH="$JAVA_HOME/bin:$PATH"

mkdir -p "$RESULT_DIR"
TMP_DIR=$(mktemp -d /tmp/derby-susom-replay.XXXXXX)
printf '%s\n' "$TMP_DIR" >"$RESULT_DIR/replay-work-directory.txt"

git clone --quiet "$TARGET_REPOSITORY" "$TMP_DIR/source"

for arm in a0 a1 a2; do
  git clone --quiet --shared "$TMP_DIR/source" "$TMP_DIR/$arm"
  git -C "$TMP_DIR/$arm" checkout --quiet --detach "$TARGET_COMMIT"
  mkdir -p "$RESULT_DIR/$arm"
done

sed -i 's#<version>10.13.1.1</version>#<version>10.14.2.0</version>#' "$TMP_DIR/a0/pom.xml"
sed -i 's#<version>10.13.1.1</version>#<version>10.15.1.3</version>#' "$TMP_DIR/a1/pom.xml" "$TMP_DIR/a2/pom.xml"
git -C "$TMP_DIR/a2" apply "$SCRIPT_DIR/susom-derbytools-maintainer-repair.patch"

{
  printf 'target_commit=%s\n' "$TARGET_COMMIT"
  java -version
  mvn -version
} >"$RESULT_DIR/environment.log" 2>&1

run_arm() {
  local arm=$1
  local worktree="$TMP_DIR/$arm"
  local output="$RESULT_DIR/$arm"

  git -C "$worktree" diff -- pom.xml >"$output/input.patch"
  set +e
  mvn -f "$worktree/pom.xml" \
    -Dmaven.repo.local="$MAVEN_REPO" \
    -Dfindbugs.skip=true \
    -Dtest="$TEST_SELECTOR" \
    -DfailIfNoTests=false \
    test >"$output/maven-test.log" 2>&1
  local status=$?
  set -e
  printf '%s\n' "$status" >"$output/exit-code.txt"

  mvn -q -f "$worktree/pom.xml" \
    -Dmaven.repo.local="$MAVEN_REPO" \
    dependency:tree \
    -Dincludes=org.apache.derby \
    -DoutputFile="$output/derby-dependency-tree.txt" \
    -DappendOutput=false >"$output/dependency-tree-command.log" 2>&1

  if [[ -d "$worktree/target/surefire-reports" ]]; then
    cp -a "$worktree/target/surefire-reports/." "$output/"
  fi
}

run_arm a0
run_arm a1
run_arm a2

run_java8_observation() {
  local arm=$1
  local worktree="$TMP_DIR/$arm"
  local output="$RESULT_DIR/java8-observation/$arm"

  mkdir -p "$output"
  set +e
  JAVA_HOME="$JAVA8_HOME" PATH="$JAVA8_HOME/bin:$PATH" mvn -f "$worktree/pom.xml" \
    -Dmaven.repo.local="$MAVEN_REPO" \
    -Dfindbugs.skip=true \
    -Dtest="$TEST_SELECTOR" \
    -DfailIfNoTests=false \
    clean test >"$output/maven-test.log" 2>&1
  local status=$?
  set -e
  printf '%s\n' "$status" >"$output/exit-code.txt"
  if [[ -d "$worktree/target/surefire-reports" ]]; then
    cp -a "$worktree/target/surefire-reports/." "$output/"
  fi
}

run_java8_observation a0
run_java8_observation a1
run_java8_observation a2

{
  class_path=org/apache/derby/jdbc/EmbeddedDriver.class
  for artifact in \
    '10.14.2.0 derby.jar|org/apache/derby/derby/10.14.2.0/derby-10.14.2.0.jar' \
    '10.15.1.3 derby.jar|org/apache/derby/derby/10.15.1.3/derby-10.15.1.3.jar' \
    '10.15.1.3 derbytools.jar|org/apache/derby/derbytools/10.15.1.3/derbytools-10.15.1.3.jar'; do
    label=${artifact%%|*}
    jar_path=${artifact#*|}
    if unzip -Z1 "$MAVEN_REPO/$jar_path" | grep -Fxq "$class_path"; then
      printf '%s: PRESENT %s\n' "$label" "$class_path"
    else
      printf '%s: ABSENT %s\n' "$label" "$class_path"
    fi
  done
} >"$RESULT_DIR/source-jar-inventory.txt"

printf 'Results written to %s\n' "$RESULT_DIR"
