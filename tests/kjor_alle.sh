#!/usr/bin/env bash
# Kjorer hele testsuiten og oppsummerer til slutt.
#
#   bash tests/kjor_alle.sh          alle tester
#   bash tests/kjor_alle.sh --rask   bare de som ikke trenger nettleser
#
# Avslutter med kode 1 hvis noe feilet, slik at GitHub Actions blir rod.

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

RASK=0
[[ "${1:-}" == "--rask" ]] && RASK=1

# Tester uten nettleser - raske, krever bare node og python3
RENE_JS=(tipping escaping kalender)
PYTHON=(test_update_data test_hent_resultater)
# Tester som starter Chromium
NETTLESER=(oppstart navigasjon feilhandtering bildekrymping)

status=0
resultat=()

kjor() {
  local navn="$1" kommando="$2"
  printf '\n\033[1m########## %s ##########\033[0m\n' "$navn"
  if eval "$kommando"; then
    resultat+=("  OK      $navn")
  else
    resultat+=("  FEILET  $navn")
    status=1
  fi
}

python3 -c 'import sys; sys.exit(0)' 2>/dev/null || { echo "python3 mangler"; exit 2; }

for t in "${PYTHON[@]}";  do kjor "$t" "python3 tests/$t.py"; done
for t in "${RENE_JS[@]}"; do kjor "$t" "node tests/$t.test.mjs"; done

if [[ $RASK -eq 1 ]]; then
  echo
  echo "(hoppet over nettlesertestene: ${NETTLESER[*]})"
else
  if [[ ! -d tests/.bilder ]] || [[ -z "$(ls -A tests/.bilder 2>/dev/null)" ]]; then
    printf '\n\033[1m########## testbilder ##########\033[0m\n'
    python3 tests/lag_testbilder.py || { echo "kunne ikke lage testbilder"; status=1; }
  fi
  for t in "${NETTLESER[@]}"; do kjor "$t" "node tests/$t.test.mjs"; done
fi

echo
echo "=================== OPPSUMMERING ==================="
printf '%s\n' "${resultat[@]}"
echo "===================================================="
[[ $status -eq 0 ]] && echo "Alt gront." || echo "Noe feilet - se over."
rm -rf scripts/__pycache__
exit $status
