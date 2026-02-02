import json
import glob
import sys

def audit_file(f_path):
    try:
        with open(f_path, 'r') as f:
            data = json.load(f)
    except Exception as e:
        return [f"Error loading: {e}"]

    # 1. Get Valid Checklist IDs
    checklist_ids = set()
    if 'plan' in data and 'spec_alignment' in data['plan'] and 'checklist' in data['plan']['spec_alignment']:
        for item in data['plan']['spec_alignment']['checklist']:
            if 'id' in item:
                checklist_ids.add(item['id'])
    
    # 2. Check Tasks for Orphans
    orphans = []
    broken_links = []
    
    if 'plan' in data and 'tasks' in data['plan']:
        for task in data['plan']['tasks']:
            t_id = task.get('task_id', 'unknown')
            t_ids = task.get('checklist_ids', [])
            
            # Check for Orphan (No parent)
            if not t_ids:
                orphans.append(t_id)
                continue
                
            # Check for Broken Links
            for link in t_ids:
                # Normalize both to upper case for comparison
                link_upper = link.upper().replace("-", "_")
                
                # Try direct match or normalized match
                found = False
                if link in checklist_ids:
                    found = True
                else:
                    # Check against normalized checklist IDs
                    # (checklist_ids set contains raw IDs, we need to iterate or normalize set first)
                    # For efficiency, let's just iterate since lists are small
                    for c_id in checklist_ids:
                        if c_id.upper().replace("-", "_") == link_upper:
                            found = True
                            break
                
                if not found:
                    broken_links.append(f"{t_id}->{link}")
                    
    errors = []
    if orphans:
        errors.append(f"Orphan Tasks (No Checklist Link): {', '.join(orphans)}")
    if broken_links:
        errors.append(f"Broken Links (ID not found): {', '.join(broken_links)}")
        
    return errors

def main():
    files = glob.glob("spec/impl_context/*.json")
    total_errors = 0
    
    print(f"Auditing {len(files)} files for v2 Migration Viability...")
    print("-" * 50)
    
    for f_path in sorted(files):
        errors = audit_file(f_path)
        if errors:
            print(f"\n[FAIL] {f_path}")
            for e in errors:
                print(f"  - {e}")
            total_errors += 1
            
    print("-" * 50)
    if total_errors == 0:
        print("SUCCESS: usage of checklist_ids is 100% complete. No orphans found.")
        print("Migration to v2 is strictly possible.")
    else:
        print(f"FAILURE: Found {total_errors} files with orphan/broken tasks.")
        print("Migration to v2 is IMPOSSIBLE without inventing requirements.")

if __name__ == "__main__":
    main()
