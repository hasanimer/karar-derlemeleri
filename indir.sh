#!/bin/zsh
# kullanım: indir.sh  — indir.tsv içindeki (ad, Drive kimliği) çiftlerini pdf/ altına indirir
cd "$(dirname "$0")"
while IFS=$'\t' read -r n id; do
  out="pdf/$n.pdf"
  [[ -s "$out" ]] && head -c 5 "$out" | grep -q '%PDF-' && { echo "VAR  $n"; continue; }
  curl -sL --retry 3 -A "Mozilla/5.0" -o "$out" "https://drive.usercontent.google.com/download?id=$id&export=download&confirm=t"
  if head -c 5 "$out" | grep -q '%PDF-'; then echo "OK   $n $(du -h "$out" | cut -f1)"; else echo "HATA $n ($(head -c 80 "$out" | tr -d '\n'))"; fi
done < indir.tsv
echo BITTI
