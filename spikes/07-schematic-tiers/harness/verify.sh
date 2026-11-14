#!/bin/bash
# verify.sh <name> <design dir> : rebuild a design with pristine make.sh/tools, gate, render at 150 dpi into verified/<name>
set -eo pipefail
X=$(dirname "$(realpath "$0")"); V=$X/verified/$1; rm -rf $V; mkdir -p $V
cp -r $X/template/make.sh $X/template/tools $V/; cp -r "$2" $V/design; rm -rf $V/design/__pycache__
$V/make.sh > $V/make.log 2>&1 && echo "$1 GATE PASS" || { echo "$1 GATE FAIL"; tail -5 $V/make.log; }
rm -f $V/out/render/*.png; pdftoppm -r 150 -png $V/out/render/sheets.pdf $V/out/render/page
