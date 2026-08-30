#!/usr/bin/env bash
# Builds Documentation.md (and Documentation.pdf when pandoc is available) from the
# numbered chapters. Run from the sme/ folder:  ./build_docs.sh
set -euo pipefail
cd "$(dirname "$0")"

PARTS=(02_Team_and_Contributions.md 03_SRS.md 04_DFD_and_Data_Model.md \
       05_Decision_Tables.md 06_Algebraic_Specifications.md \
       07_WBS_Activity_Network_PERT.md 08_Test_Cases.md)

{
  echo "---"
  echo "title: \"High Table Holdings v4 — Project Documentation\""
  echo "subtitle: \"Software Engineering & Management, SEM 2026-27\""
  echo "date: \"$(date +%d\ %B\ %Y)\""
  echo "toc: true"
  echo "toc-depth: 2"
  echo "geometry: margin=2cm"
  echo "---"
  for f in "${PARTS[@]}"; do
    cat "$f"
    printf '\n\n\\newpage\n\n'
  done
} > Documentation.md
echo "wrote Documentation.md"

if command -v pandoc >/dev/null 2>&1; then
  if command -v mmdc >/dev/null 2>&1 && pandoc --list-filters 2>/dev/null | grep -q mermaid-filter; then
    pandoc Documentation.md -o Documentation.pdf -F mermaid-filter --pdf-engine=xelatex
  else
    echo "mermaid-filter / mmdc not found - diagrams will appear as code blocks." >&2
    pandoc Documentation.md -o Documentation.pdf --pdf-engine=xelatex
  fi
  echo "wrote Documentation.pdf"
else
  echo "pandoc not installed - open Documentation.md in VS Code (Markdown Preview Enhanced) and export to PDF." >&2
fi
