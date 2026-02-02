import json
import jsonschema
import os

SCHEMA_PATH = "devspec_toolkit/schema/02a_delivery_baseline.schema.json"

def load_schema():
    with open(SCHEMA_PATH, 'r') as f:
        schema = json.load(f)
    return schema

def test_positive_case():
    print("Running Positive Case...")
    valid_data = {
        "id": "delivery-baseline-catalog",
        "owner": "api",
        "created_at": "2025-01-01T00:00:00Z",
        "environments": {
            "dev": { "region": "us-east-1" },
            "ci": { "runner": "ubuntu-latest" },
            "staging": { "region": "us-east-1" },
            "prod": { "region": "us-east-1" }
        },
        "ci_gates": ["schema-validate"],
        "trace": [
            { "type": "capability", "id": "cap-system" }
        ]
    }
    schema = load_schema()
    try:
        # Minimal resolver mock if needed, but simple validation might work if refs are resolvable or ignored
        # For this script we assume local refs might fail if not fully resolved, but let's try basic validation
        # or just validate locally if no external refs.
        # The schema uses $ref to core. We might need a proper registry.
        # Actually, let's use the CLI tool if possible, or just mock the refs for this quick check.
        # But wait, I can just use the internal CLI `python -m specdev_tools.cli validate` ?
        # Let's write artifacts and run the CLI.
        pass
    except Exception as e:
        print(f"Validation error: {e}")

# Actually, better to write files and use the CLI tool validation which handles refs.
with open("valid_02a.json", "w") as f:
    json.dump({
        "id": "delivery-baseline-catalog",
        "owner": "api",
        "created_at": "2025-01-01T00:00:00Z",
        "environments": {
            "dev": { "region": "us-east-1" },
            "ci": { "runner": "ubuntu-latest" },
            "staging": { "region": "us-east-1" },
            "prod": { "region": "us-east-1" }
        },
        "ci_gates": ["schema-validate"],
        "trace": [
            { "type": "capability", "id": "cap-system" }
        ]
    }, f)

with open("invalid_empty_env.json", "w") as f:
    json.dump({
        "id": "delivery-baseline-catalog",
        "owner": "api",
        "created_at": "2025-01-01T00:00:00Z",
        "environments": {
            "dev": {},
            "ci": { "runner": "ubuntu-latest" },
            "staging": { "region": "us-east-1" },
            "prod": { "region": "us-east-1" }
        },
        "ci_gates": ["schema-validate"]
    }, f)

print("Generated test files.")
