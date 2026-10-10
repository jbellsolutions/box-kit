#!/bin/zsh
# FLEET_SCRATCH: the scratch dir that holds py/.venv (browser-use, stagehand) and receives the outputs.
PY="${FLEET_SCRATCH:?set FLEET_SCRATCH}/py/.venv/bin/python"
S="$(cd "$(dirname "$0")" && pwd)/capture_browseruse.py"
B="$FLEET_SCRATCH/spikes/reasoning-models/bu_live"
T1="Go to https://quotes.toscrape.com/ , use the Next button to go to page 3, and report the author of the first quote on page 3."
T2="Go to https://the-internet.herokuapp.com/dynamic_loading/2 , click the Start button, wait for the loading to finish, and report the exact text that appears."
for r in 1 2 3; do
  timeout 300 $PY $S $B/glm_q_$r z-ai/glm-5.3-flash 8 box "$T1" > /dev/null 2>&1; echo "glm q $r: $(cat $B/glm_q_$r/bu_summary.json 2>/dev/null | tr '\n' ' ' | cut -c1-300)"
  timeout 300 $PY $S $B/ds_q_$r deepseek/deepseek-v4.1-flash 8 or-off "$T1" > /dev/null 2>&1; echo "ds q $r: $(cat $B/ds_q_$r/bu_summary.json 2>/dev/null | tr '\n' ' ' | cut -c1-300)"
  timeout 300 $PY $S $B/glm_d_$r z-ai/glm-5.3-flash 8 box "$T2" > /dev/null 2>&1; echo "glm d $r: $(cat $B/glm_d_$r/bu_summary.json 2>/dev/null | tr '\n' ' ' | cut -c1-300)"
  timeout 300 $PY $S $B/ds_d_$r deepseek/deepseek-v4.1-flash 8 or-off "$T2" > /dev/null 2>&1; echo "ds d $r: $(cat $B/ds_d_$r/bu_summary.json 2>/dev/null | tr '\n' ' ' | cut -c1-300)"
done
echo BU_LIVE_DONE
