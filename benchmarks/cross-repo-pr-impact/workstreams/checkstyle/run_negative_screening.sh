#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "用法：$0 <Elementary 克隆> <Conventional Commit Linter 克隆> <结果目录>" >&2
  exit 2
fi

elementary_repo=$1
linter_repo=$2
output=$(realpath -m "$3")
mkdir -p "$output"

export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
export PATH="$JAVA_HOME/bin:$PATH"
agent=$HOME/.m2/repository/org/jacoco/org.jacoco.agent/0.8.12/org.jacoco.agent-0.8.12-runtime.jar
cli=$HOME/.m2/repository/org/jacoco/org.jacoco.cli/0.8.12/org.jacoco.cli-0.8.12-nodeps.jar
checkstyle_jar=$HOME/.m2/repository/com/puppycrawl/tools/checkstyle/10.12.2/checkstyle-10.12.2.jar

set_version() {
  local repo_dir=$1
  local version=$2
  local current_count
  current_count=$(rg -c '<version>10\.12\.1</version>' "$repo_dir/pom.xml")
  if [[ "$current_count" -ne 1 ]]; then
    echo "期望 $repo_dir/pom.xml 恰有一个 Checkstyle 10.12.1 插件依赖，实际为 $current_count" >&2
    return 1
  fi
  sed -i "s#<version>10\.12\.1</version>#<version>${version}</version>#" "$repo_dir/pom.xml"
  rg -n -B2 -A1 "<version>${version//./\\.}</version>" "$repo_dir/pom.xml"
}

run_repo() {
  local name=$1
  local repo_dir=$2
  local commit=$3
  local profile=$4
  local version

  for version in 10.12.1 10.12.2; do
    git -C "$repo_dir" checkout --detach --force "$commit" >"$output/${name}-${version}-checkout.log" 2>&1
    set_version "$repo_dir" "$version" >"$output/${name}-${version}-version-edit.log" 2>&1
    local exec_file="$output/${name}-${version}.exec"
    local profile_args=()
    if [[ -n "$profile" ]]; then
      profile_args+=("-P$profile")
    fi
    set +e
    (
      cd "$repo_dir"
      if [[ "$name" == elementary ]]; then
        MAVEN_OPTS="-javaagent:$agent=destfile=$exec_file,append=false" \
          mvn -B clean checkstyle:check
      else
        MAVEN_OPTS="-javaagent:$agent=destfile=$exec_file,append=false" \
          mvn -B "${profile_args[@]}" clean validate
      fi
    ) >"$output/${name}-${version}.log" 2>&1
    local status=$?
    set -e
    printf '%s\n' "$status" >"$output/${name}-${version}.exit"
  done

  java -jar "$cli" report "$output/${name}-10.12.2.exec" \
    --classfiles "$checkstyle_jar" \
    --xml "$output/${name}-checkstyle-10.12.2.xml" >"$output/${name}-report.log" 2>&1

  local summary="$output/${name}-final-class-change-coverage.tsv"
  printf 'line\tmissed_instructions\tcovered_instructions\tmissed_branches\tcovered_branches\n' \
    >"$summary"
  local line attribute value
  for line in 247 249 250 283 284 285 286 288 289 291 292 294 295 297 573 574 575 643 644 652 653; do
    printf '%s' "$line" >>"$summary"
    for attribute in mi ci mb cb; do
      value=$(xmllint --xpath \
        "string(//sourcefile[@name='FinalClassCheck.java']/line[@nr='$line']/@$attribute)" \
        "$output/${name}-checkstyle-10.12.2.xml")
      printf '\t%s' "${value:-0}" >>"$summary"
    done
    printf '\n' >>"$summary"
  done
  rm "$output/${name}-checkstyle-10.12.2.xml"
}

run_repo elementary "$elementary_repo" 2c058f2fceda99fca5b9a709105fe082dd75f32b '' &
pid_elementary=$!
run_repo conventional-commit-linter "$linter_repo" 665f517d2cd056243633e587c22f138b3ca50a57 quality &
pid_linter=$!
wait "$pid_elementary"
wait "$pid_linter"

printf 'repository\tversion\texit_code\n' >"$output/run-results.tsv"
for repository in elementary conventional-commit-linter; do
  for version in 10.12.1 10.12.2; do
    printf '%s\t%s\t%s\n' "$repository" "$version" \
      "$(<"$output/${repository}-${version}.exit")" >>"$output/run-results.tsv"
  done
done
