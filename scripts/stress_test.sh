#!/bin/bash
# Zyphos Full System Stress Test
cd ~/zyp
source venv/bin/activate

echo "========================================"
echo "ZYPHOS FULL SYSTEM STRESS TEST"
echo "========================================"

echo ""
echo "--- TEST 1: Plugin Load Time ---"
python -c "
from core.plugin_loader import load_plugins
import time
s = time.time()
p = load_plugins()
print(f'{len(p)} plugins loaded in {time.time()-s:.2f}s')
"

echo ""
echo "--- TEST 2: Sequential Diverse Goals (12 tools) ---"
goals=(
    "take a screenshot"
    "what is 47 times 89"
    "tell me a joke"
    "define the word ubiquitous"
    "translate hello to spanish"
    "what is the weather in Delhi"
    "search for rust programming language"
    "tell me a philosophical quote"
    "generate a qr code for https://github.com"
    "what country is Paris in"
    "get github stats for torvalds/linux"
    "give me my morning briefing"
)
start_time=$(date +%s)
for goal in "${goals[@]}"; do
    echo ">>> $goal"
    timeout 60 python zyphos.py --smart --smart-plan --critique "$goal" 2>&1 | grep -E "✓|CRITIC|GOAL|error|Error|Traceback" | head -8
    echo "---"
done
end_time=$(date +%s)
echo "Total time for 12 diverse goals: $((end_time - start_time))s"

echo ""
echo "--- TEST 3: Rapid Daemon Queue (20 goals) ---"
start_time=$(date +%s)
for i in {1..20}; do
    python zyphos.py --send "test goal $i" 2>&1 | grep -v PLUGIN | grep -v Warning
done
end_time=$(date +%s)
echo "Queued 20 goals in $((end_time - start_time))s"
echo "Clearing test queue to prevent daemon from processing junk goals later..."
echo "" > ~/zyp/state/pending_goals.txt

echo ""
echo "--- TEST 4: Memory Recall Speed at Scale ---"
python -c "
from memory.store import recall
import time
s = time.time()
results = recall('screenshot', top_k=5)
print(f'Recall took {time.time()-s:.2f}s, found {len(results)} results')
"

echo ""
echo "--- TEST 5: Concurrent Plugin Calls (threading) ---"
python -c "
import concurrent.futures
import time
from plugins.calculator import run as calc_run
from plugins.dictionary import run as dict_run

def task(i):
    if i % 2 == 0:
        return calc_run({'expression': f'{i} * {i}'})
    else:
        return dict_run({'word': 'test'})

s = time.time()
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
    results = list(executor.map(task, range(10)))
print(f'10 concurrent plugin calls in {time.time()-s:.2f}s')
print(f'All succeeded: {all(r.get(\"status\") == \"ok\" for r in results)}')
"

echo ""
echo "--- TEST 6: Malformed/Edge Case Goals ---"
edge_goals=(
    "asdkjaslkdjalksjd"
    "take a screenshot"
    "what is the meaning of life the universe and everything"
)
for goal in "${edge_goals[@]}"; do
    echo ">>> $goal"
    timeout 30 python zyphos.py --smart --smart-plan "$goal" 2>&1 | grep -E "✓|error|Error|Traceback" | head -8
done

echo ""
echo "--- TEST 7: Daemon + Watchdog + Reminder Health Check ---"
pgrep -f "zyphos.py --daemon" > /dev/null && echo "Daemon: RUNNING" || echo "Daemon: NOT RUNNING"
pgrep -f "event_reminder.py" > /dev/null && echo "Reminder: RUNNING" || echo "Reminder: NOT RUNNING"
pgrep -f "watchdog.py" > /dev/null && echo "Watchdog: RUNNING" || echo "Watchdog: NOT RUNNING"

echo ""
echo "--- CLEANUP ---"
python zyphos.py --forget "test goal" 2>&1 | grep FORGET

echo ""
echo "========================================"
echo "STRESS TEST COMPLETE"
echo "========================================"
