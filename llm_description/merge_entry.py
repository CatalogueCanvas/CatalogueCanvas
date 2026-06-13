"""
merge_entry.py — upsert one item entry into llm_descriptions.json.

Usage: echo '<json>' | python3 merge_entry.py <json_path> <item_id>
Reads the entry from stdin, merges it into the output file (creates if missing).
"""
import sys
import json

json_path, item_id = sys.argv[1:]

# Read the entry produced by describe_one.py from stdin
entry = json.loads(sys.stdin.read())

# Load existing descriptions; start fresh if file is missing or corrupt
try:
    data = json.loads(open(json_path).read())
except (FileNotFoundError, json.JSONDecodeError):
    data = {}

data[item_id] = entry
open(json_path, "w").write(json.dumps(data, indent=2, ensure_ascii=False))
