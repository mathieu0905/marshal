#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 5 ]]; then
  echo "用法：$0 <Gauge Java 克隆> <WSS4J 克隆> <Elementary 克隆> <Conventional Commit Linter 克隆> <结果目录>" >&2
  exit 2
fi

gauge_repo=$1
wss_repo=$2
elementary_repo=$3
linter_repo=$4
output=$(realpath -m "$5")
mkdir -p "$output"

export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
export PATH="$JAVA_HOME/bin:$PATH"
agent=$HOME/.m2/repository/org/jacoco/org.jacoco.agent/0.8.12/org.jacoco.agent-0.8.12-runtime.jar
cli=$HOME/.m2/repository/org/jacoco/org.jacoco.cli/0.8.12/org.jacoco.cli-0.8.12-nodeps.jar
checkstyle_jar=$HOME/.m2/repository/com/puppycrawl/tools/checkstyle/10.12.3/checkstyle-10.12.3.jar

set_version() {
  local repo_dir=$1
  local version=$2
  local current_count
  current_count=$(rg -c '<version>10\.12\.[12]</version>' "$repo_dir/pom.xml")
  if [[ "$current_count" -ne 1 ]]; then
    echo "期望 $repo_dir/pom.xml 恰有一个 Checkstyle 10.12.1/10.12.2 插件依赖，实际为 $current_count" >&2
    return 1
  fi
  sed -Ei "s#<version>10\.12\.[12]</version>#<version>${version}</version>#" "$repo_dir/pom.xml"
  rg -n -B2 -A1 "<version>${version//./\\.}</version>" "$repo_dir/pom.xml"
}

write_coverage() {
  local name=$1
  local xml=$2
  local summary="$output/${name}-a3-change-coverage.tsv"
  printf 'source\tline\tmissed_instructions\tcovered_instructions\tmissed_branches\tcovered_branches\n' \
    >"$summary"
  local source line attribute value
  while read -r source line; do
    printf '%s\t%s' "$source" "$line" >>"$summary"
    for attribute in mi ci mb cb; do
      value=$(xmllint --xpath \
        "string(//sourcefile[@name='$source']/line[@nr='$line']/@$attribute)" "$xml")
      printf '\t%s' "${value:-0}" >>"$summary"
    done
    printf '\n' >>"$summary"
  done <<'EOF'
JavaAstVisitor.java 1238
JavaAstVisitor.java 1299
JavaAstVisitor.java 1300
JavaAstVisitor.java 1301
JavaAstVisitor.java 1302
JavaAstVisitor.java 1303
ModifiedControlVariableCheck.java 326
ModifiedControlVariableCheck.java 328
ModifiedControlVariableCheck.java 329
ModifiedControlVariableCheck.java 330
ModifiedControlVariableCheck.java 340
ModifiedControlVariableCheck.java 341
ModifiedControlVariableCheck.java 342
ModifiedControlVariableCheck.java 343
ModifiedControlVariableCheck.java 345
UnnecessarySemicolonAfterTypeMemberDeclarationCheck.java 204
EOF
}

run_repo() {
  local name=$1
  local repo_dir=$2
  local commit=$3
  shift 3
  local version

  for version in 10.12.2 10.12.3; do
    git -C "$repo_dir" checkout --detach --force "$commit" >"$output/${name}-${version}-checkout.log" 2>&1
    set_version "$repo_dir" "$version" >"$output/${name}-${version}-version-edit.log" 2>&1
    local exec_file="$output/${name}-${version}.exec"
    set +e
    (
      cd "$repo_dir"
      if [[ "$name" == gauge-java ]]; then
        MAVEN_OPTS="-javaagent:$agent=destfile=$exec_file,append=false" \
          mvn -B clean validate
      else
        MAVEN_OPTS="-javaagent:$agent=destfile=$exec_file,append=false" \
          mvn -B "$@" clean checkstyle:check
      fi
    ) >"$output/${name}-${version}.log" 2>&1
    local status=$?
    set -e
    printf '%s\n' "$status" >"$output/${name}-${version}.exit"
  done

  local xml="$output/${name}-checkstyle-10.12.3.xml"
  java -jar "$cli" report "$output/${name}-10.12.3.exec" \
    --classfiles "$checkstyle_jar" --xml "$xml" >"$output/${name}-report.log" 2>&1
  write_coverage "$name" "$xml"
  rm "$xml"
}

run_repo gauge-java "$gauge_repo" db1a09cc0db2b8045a5c2da34617136cd4290fc7 &
pid_gauge=$!
run_repo ws-wss4j "$wss_repo" d1347cb288174bb6442913fce2919945b05da136 -pl ws-security-stax &
pid_wss=$!
run_repo elementary "$elementary_repo" 2c058f2fceda99fca5b9a709105fe082dd75f32b &
pid_elementary=$!
run_repo conventional-commit-linter "$linter_repo" 665f517d2cd056243633e587c22f138b3ca50a57 -Pquality &
pid_linter=$!

wait "$pid_gauge"
wait "$pid_wss"
wait "$pid_elementary"
wait "$pid_linter"

printf 'repository\tversion\texit_code\n' >"$output/run-results.tsv"
for repository in gauge-java ws-wss4j elementary conventional-commit-linter; do
  for version in 10.12.2 10.12.3; do
    printf '%s\t%s\t%s\n' "$repository" "$version" \
      "$(<"$output/${repository}-${version}.exit")" >>"$output/run-results.tsv"
  done
done
