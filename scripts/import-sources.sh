#!/bin/sh
# Replace one managed source volume from an explicit local directory.
set -eu

if [ "$#" -ne 2 ]; then
  echo "usage: $0 <campaign|rules> <source-directory>" >&2
  exit 2
fi

kind=$1
source_directory=$2
CONTAINER_ENGINE=${CONTAINER_ENGINE:-docker}

case "$kind" in
  campaign)
    volume=${DM_CAMPAIGN_SOURCE_VOLUME:-dm-assistant-campaign-sources}
    ;;
  rules)
    volume=${DM_RULES_SOURCE_VOLUME:-dm-assistant-rules-sources}
    ;;
  *)
    echo "source kind must be campaign or rules" >&2
    exit 2
    ;;
esac

if [ ! -d "$source_directory" ]; then
  echo "source directory does not exist: $source_directory" >&2
  exit 1
fi

source_directory=$(cd "$source_directory" && pwd -P)
if [ -n "$(find "$source_directory" -type l -print -quit)" ]; then
  echo "source directory cannot contain symbolic links" >&2
  exit 1
fi

"$CONTAINER_ENGINE" volume create "$volume" >/dev/null
"$CONTAINER_ENGINE" run --rm \
  -v "$volume:/destination" \
  -v "$source_directory:/source:ro" \
  docker.io/library/busybox:1.37.0 \
  sh -ec '
    rm -rf /destination/.incoming /destination/.previous
    mkdir -p /destination/.incoming
    cp -R /source/. /destination/.incoming/
    chmod -R a+rX /destination/.incoming
    if [ -e /destination/current ]; then
      mv /destination/current /destination/.previous
    fi
    mv /destination/.incoming /destination/current
    rm -rf /destination/.previous
  '

echo "Imported $kind sources from $source_directory into managed volume $volume."
echo "Run the Library ingestion command to create immutable document revisions."
