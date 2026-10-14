#!/usr/bin/env bash
# Build odmrp-java-node.jar (fat jar with Gson).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
JAVA_HOME="${JAVA_HOME:-${HOME}/tools/jdk}"
if [[ ! -x "${JAVA_HOME}/bin/javac" ]]; then
  JAVA_HOME="$(dirname "$(dirname "$(command -v javac)")")"
fi
export PATH="${JAVA_HOME}/bin:${PATH}"

LIB="${ROOT}/lib/gson-2.11.0.jar"
SRC_ROOT="${ROOT}/src/main/java"
OUT="${ROOT}/build/classes"
DIST="${ROOT}/dist"
JAR="${DIST}/odmrp-java-node.jar"

if [[ ! -f "${LIB}" ]]; then
  echo "Missing ${LIB}. Download Gson 2.11.0 into java-node/lib/" >&2
  exit 1
fi

rm -rf "${OUT}"
mkdir -p "${OUT}" "${DIST}"
mapfile -t SOURCES < <(find "${SRC_ROOT}" -name '*.java' | sort)
javac --release 17 -cp "${LIB}" -d "${OUT}" "${SOURCES[@]}"

# Stage classes + extract Gson into a single jar
STAGE="${ROOT}/build/stage"
rm -rf "${STAGE}"
mkdir -p "${STAGE}"
cp -a "${OUT}/." "${STAGE}/"
( cd "${STAGE}" && jar xf "${LIB}" )
rm -rf "${STAGE}/META-INF/MANIFEST.MF" "${STAGE}/META-INF/maven"
printf 'Manifest-Version: 1.0\nMain-Class: odmrp.Main\n' > "${ROOT}/build/MANIFEST.MF"
jar cfm "${JAR}" "${ROOT}/build/MANIFEST.MF" -C "${STAGE}" .
echo "Built ${JAR}"
java -jar "${JAR}" <<<'{"op":"configure","id":1,"node_id":0,"params":{},"rng_seed":1}
{"op":"get_state","id":2}
{"op":"shutdown","id":3}' | head -5
