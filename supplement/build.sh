#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
rm -f supplement.aux supplement.log supplement.out supplement.pdf supplement.toc
pdflatex -interaction=nonstopmode -halt-on-error supplement.tex > build-pass1.log
pdflatex -interaction=nonstopmode -halt-on-error supplement.tex > build-pass2.log
pdflatex -interaction=nonstopmode -halt-on-error supplement.tex > build-pass3.log
