#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd "$SCRIPT_DIR/../../../.." && pwd)
WORK_DIR="$ROOT_DIR/.work/mockwebserver-4.0-fse/probe-run"
LIB_DIR="$WORK_DIR/lib"
CLASS_DIR="$WORK_DIR/classes"
RESULT_DIR="$ROOT_DIR/benchmarks/cross-repo-pr-impact/results/mockwebserver-4.0-fse-history-screening-2026-08-25"
JAVA=${JAVA:-/usr/bin/java}

mkdir -p "$LIB_DIR" "$CLASS_DIR" "$RESULT_DIR"

fetch() {
  local name=$1
  local url=$2
  if [[ ! -f "$LIB_DIR/$name" ]]; then
    curl -L --fail --silent --show-error -o "$LIB_DIR/$name" "$url"
  fi
}

fetch ecj.jar https://repo1.maven.org/maven2/org/eclipse/jdt/ecj/3.33.0/ecj-3.33.0.jar
fetch mockwebserver-4.0.0.jar https://repo1.maven.org/maven2/com/squareup/okhttp3/mockwebserver/4.0.0/mockwebserver-4.0.0.jar
fetch okhttp-4.0.0.jar https://repo1.maven.org/maven2/com/squareup/okhttp3/okhttp/4.0.0/okhttp-4.0.0.jar
fetch okhttp-3.12.0.jar https://repo1.maven.org/maven2/com/squareup/okhttp3/okhttp/3.12.0/okhttp-3.12.0.jar
fetch okio-2.2.2.jar https://repo1.maven.org/maven2/com/squareup/okio/okio/2.2.2/okio-2.2.2.jar
fetch okio-1.17.5.jar https://repo1.maven.org/maven2/com/squareup/okio/okio/1.17.5/okio-1.17.5.jar
fetch okio-1.15.0.jar https://repo1.maven.org/maven2/com/squareup/okio/okio/1.15.0/okio-1.15.0.jar
fetch kotlin-stdlib-1.3.40.jar https://repo1.maven.org/maven2/org/jetbrains/kotlin/kotlin-stdlib/1.3.40/kotlin-stdlib-1.3.40.jar
fetch junit-4.12.jar https://repo1.maven.org/maven2/junit/junit/4.12/junit-4.12.jar

COMPILE_CP="$LIB_DIR/mockwebserver-4.0.0.jar:$LIB_DIR/okhttp-4.0.0.jar:$LIB_DIR/okio-2.2.2.jar:$LIB_DIR/kotlin-stdlib-1.3.40.jar:$LIB_DIR/junit-4.12.jar"
"$JAVA" -jar "$LIB_DIR/ecj.jar" -source 8 -target 8 -cp "$COMPILE_CP" -d "$CLASS_DIR" \
  "$SCRIPT_DIR/MockWebServerConstructorProbe.java" "$SCRIPT_DIR/ServiceInvokerStaticProbe.java"

"$JAVA" -cp "$CLASS_DIR:$LIB_DIR/mockwebserver-4.0.0.jar:$LIB_DIR/okhttp-4.0.0.jar:$LIB_DIR/okio-2.2.2.jar:$LIB_DIR/kotlin-stdlib-1.3.40.jar:$LIB_DIR/junit-4.12.jar" \
  MockWebServerConstructorProbe 2>&1 | tee "$RESULT_DIR/jsonapi-aligned.log"

"$JAVA" -cp "$CLASS_DIR:$LIB_DIR/mockwebserver-4.0.0.jar:$LIB_DIR/okhttp-3.12.0.jar:$LIB_DIR/okio-1.15.0.jar:$LIB_DIR/kotlin-stdlib-1.3.40.jar:$LIB_DIR/junit-4.12.jar" \
  MockWebServerConstructorProbe 2>&1 | tee "$RESULT_DIR/jsonapi-skew.log"

"$JAVA" -cp "$CLASS_DIR:$LIB_DIR/okhttp-4.0.0.jar:$LIB_DIR/okio-2.2.2.jar:$LIB_DIR/kotlin-stdlib-1.3.40.jar" \
  ServiceInvokerStaticProbe 2>&1 | tee "$RESULT_DIR/opengamma-aligned.log"

"$JAVA" -cp "$CLASS_DIR:$LIB_DIR/okhttp-4.0.0.jar:$LIB_DIR/okio-1.17.5.jar:$LIB_DIR/kotlin-stdlib-1.3.40.jar" \
  ServiceInvokerStaticProbe 2>&1 | tee "$RESULT_DIR/opengamma-skew.log"
