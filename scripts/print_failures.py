# -*- coding: utf-8 -*-
import json

with open('scripts/gaman_slash_audit_results.json', encoding='utf-8') as f:
    d = json.load(f)

fails = [x for x in d if x['test_result'] != 'PASS']
print(f"Total non-pass: {len(fails)}")
for x in fails:
    print(f"[{x['test_result']}] /{x['command']} (sub: {x['subcommand']}) -> {x['actual_behavior']} (Root Cause: {x['root_cause']})")
