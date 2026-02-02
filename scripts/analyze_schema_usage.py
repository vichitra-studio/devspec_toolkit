import json
import glob
import os
from collections import defaultdict, Counter

def analyze_keys(data, prefix="", keys_set=None, metadata_counter=None):
    if keys_set is None:
        keys_set = set()
    if metadata_counter is None:
        metadata_counter = Counter()

    if isinstance(data, dict):
        for k, v in data.items():
            full_key = f"{prefix}.{k}" if prefix else k
            keys_set.add(full_key)
            
            if k == "metadata" and isinstance(v, dict):
                for meta_k in v.keys():
                    metadata_counter[f"{full_key}.{meta_k}"] += 1
            
            analyze_keys(v, full_key, keys_set, metadata_counter)
    elif isinstance(data, list):
        for item in data:
            analyze_keys(item, prefix, keys_set, metadata_counter)
            
    return keys_set, metadata_counter

def main():
    files = glob.glob("spec/impl_context/*.json")
    all_keys = set()
    metadata_stats = Counter()
    
    print(f"Scanning {len(files)} files...")
    
    for f_path in files:
        try:
            with open(f_path, 'r') as f:
                data = json.load(f)
                analyze_keys(data, "", all_keys, metadata_stats)
        except Exception as e:
            print(f"Error reading {f_path}: {e}")

    print("\n=== Unique Schema Keys Found ===")
    for k in sorted(all_keys):
        if "metadata" not in k: # Hide metadata contents here to reduce noise
            print(k)

    print("\n=== Metadata Field Usage ===")
    for k, count in metadata_stats.most_common():
        print(f"{count:4d} : {k}")

if __name__ == "__main__":
    main()
