#!/bin/zsh
# kullanım: cevir.sh <pdf>  — bir derlemeyi yoklar, dönüştürür, doğrular; çıktı ara/<ad>/, günlük log/<ad>.log (ardından: python3 yapi.py)
# ek/<ad>.args varsa içindeki seçenekler probe ve convert'e eklenir
cd "$(dirname "$0")"; P="${PDF2MD:-$HOME/.claude/skills/pdf-md/scripts/pdf2md.py}"
f="$1"; n="${f:t:r}"; mkdir -p log ara
extra=(); [[ -f "ek/$n.args" ]] && extra=(${(z)"$(<ek/$n.args)"})
{
  first=$(uv run -q "$P" probe "$f" | sed -nE 's/^Yer imi.*ilki s\. ([0-9]+):.*/\1/p'); first=${first:-1}
  pages=$(uv run -q "$P" probe "$f" --start-page $first $extra | tee /dev/stderr | sed -nE 's/^Sayfa +: ([0-9]+).*/\1/p') 2>&1
  echo "=== convert (start-page $first ${extra[*]})"
  uv run -q "$P" convert "$f" "ara/$n" --start-page $first --strip-colon $extra
  echo "=== verify"
  uv run -q "$P" verify "ara/$n/$n.md" "$f" --show 12
  echo "=== exit $?"
} > "log/$n.log" 2>&1
echo "$n: $(grep -E '^Sonuç:' log/$n.log | cut -c1-80)"
