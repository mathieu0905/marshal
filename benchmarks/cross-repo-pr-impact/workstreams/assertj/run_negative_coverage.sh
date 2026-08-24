#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "用法：$0 <db-a1 克隆> <examples-a1 克隆> <结果目录>" >&2
  exit 2
fi

db_repo=$1
examples_repo=$2
output=$(realpath -m "$3")
mkdir -p "$output"

export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
export PATH="$JAVA_HOME/bin:$PATH"
agent=$HOME/.m2/repository/org/jacoco/org.jacoco.agent/0.8.12/org.jacoco.agent-0.8.12-runtime.jar
cli=$HOME/.m2/repository/org/jacoco/org.jacoco.cli/0.8.12/org.jacoco.cli-0.8.12-nodeps.jar
core_jar=$HOME/.m2/repository/org/assertj/assertj-core/3.23.0/assertj-core-3.23.0.jar

if [[ ! -f "$agent" || ! -f "$cli" || ! -f "$core_jar" ]]; then
  echo "缺少 JaCoCo 0.8.12 或 AssertJ Core 3.23.0 本地制品" >&2
  exit 3
fi

append_line_coverage() {
  local repository=$1
  local source=$2
  local line=$3
  local package=${source%/*}
  local file=${source##*/}
  local xml="$output/${repository}-assertj-core.xml"
  local node

  node=$(xmllint --xpath \
    "//package[@name='$package']/sourcefile[@name='$file']/line[@nr='$line']" \
    "$xml")
  printf '%s\t%s\t%s\t%s\n' "$repository" "$source" "$line" "$node" \
    >>"$output/changed-line-coverage.tsv"
}

run_db() {
  git -C "$db_repo" checkout --detach --force 8aefa0f0417aa5cf01a9990ff554a119a6ddf557 >"$output/assertj-db-checkout.log" 2>&1
  (
    cd "$db_repo"
    mvn -B versions:use-dep-version \
      -Dincludes=org.assertj:assertj-core \
      -DdepVersion=3.23.0 \
      -DforceVersion=true \
      -DgenerateBackupPoms=false
  ) >"$output/assertj-db-version-edit.log" 2>&1
  (
    cd "$db_repo"
    mvn -B test \
      -Djacoco.skip=true \
      -Dtest=org.assertj.db.api.SoftAssertions_Test \
      -DargLine="-javaagent:$agent=destfile=$output/assertj-db.exec"
  ) >"$output/assertj-db.log" 2>&1
  java -jar "$cli" report "$output/assertj-db.exec" \
    --classfiles "$core_jar" \
    --xml "$output/assertj-db-assertj-core.xml" >"$output/assertj-db-report.log" 2>&1
}

run_examples() {
  git -C "$examples_repo" checkout --detach --force 0868b5d724374ca0eb3f6c2456b27acd5ac740e0 >"$output/assertj-examples-checkout.log" 2>&1
  (
    cd "$examples_repo"
    JAVA_TOOL_OPTIONS="-javaagent:$agent=destfile=$output/assertj-examples.exec,append=true" \
    mvn -B -f assertions-examples/pom.xml test \
      -Dassertj-core.version=3.23.0 \
      -Dtest=org.assertj.examples.SoftAssertionsExamples#host_dinner_party_where_nobody_dies
  ) >"$output/assertj-examples.log" 2>&1
  java -jar "$cli" report "$output/assertj-examples.exec" \
    --classfiles "$core_jar" \
    --xml "$output/assertj-examples-assertj-core.xml" >"$output/assertj-examples-report.log" 2>&1
}

run_db &
pid_db=$!
run_examples &
pid_examples=$!
wait "$pid_db"
wait "$pid_examples"

printf 'repository\tsource_file\tline\tjacoco_line_node\n' >"$output/changed-line-coverage.tsv"
while read -r repository source line; do
  append_line_coverage "$repository" "$source" "$line"
done <<'EOF'
assertj-db org/assertj/core/api/AssertionsForInterfaceTypes.java 187
assertj-db org/assertj/core/api/ListAssert.java 48
assertj-examples org/assertj/core/api/DefaultAssertionErrorCollector.java 141
assertj-examples org/assertj/core/error/AssertJMultipleFailuresError.java 50
assertj-examples org/assertj/core/error/AssertJMultipleFailuresError.java 53
assertj-examples org/assertj/core/util/Throwables.java 185
assertj-examples org/assertj/core/util/Throwables.java 186
assertj-examples org/assertj/core/util/Throwables.java 187
assertj-examples org/assertj/core/util/Throwables.java 191
assertj-examples org/assertj/core/util/Throwables.java 192
assertj-examples org/assertj/core/util/Throwables.java 193
assertj-examples org/assertj/core/util/Throwables.java 194
assertj-examples org/assertj/core/util/Throwables.java 195
assertj-examples org/assertj/core/util/Throwables.java 196
assertj-examples org/assertj/core/util/Throwables.java 197
assertj-examples org/assertj/core/util/Throwables.java 198
assertj-examples org/assertj/core/util/Throwables.java 199
assertj-examples org/assertj/core/util/Throwables.java 200
assertj-examples org/assertj/core/util/Throwables.java 201
assertj-examples org/assertj/core/util/Throwables.java 202
assertj-examples org/assertj/core/util/Throwables.java 203
assertj-examples org/assertj/core/util/Throwables.java 204
assertj-examples org/assertj/core/util/Throwables.java 205
assertj-examples org/assertj/core/util/Throwables.java 206
assertj-examples org/assertj/core/util/Throwables.java 207
assertj-examples org/assertj/core/util/Throwables.java 208
assertj-examples org/assertj/core/util/Throwables.java 212
assertj-examples org/assertj/core/util/Throwables.java 216
assertj-examples org/assertj/core/util/Throwables.java 220
assertj-examples org/assertj/core/util/Throwables.java 221
assertj-examples org/assertj/core/util/Throwables.java 226
EOF

rm "$output/assertj-db-assertj-core.xml" "$output/assertj-examples-assertj-core.xml"
