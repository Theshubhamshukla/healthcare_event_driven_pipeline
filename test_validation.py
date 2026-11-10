import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path("cloud_function").resolve()))

from main import validate_record

sample_dir = Path("sample_data")

total = 0
valid = 0
rejected = 0

for file_path in sorted(sample_dir.glob("*.json")):
    print(f"\nFile: {file_path.name}")

    for line in file_path.read_text().splitlines():
        if not line.strip():
            continue

        total += 1
        record = json.loads(line)
        reason = validate_record(record)

        if reason is None:
            valid += 1
            print(f"VALID: {record.get('patient_id')}")
        else:
            rejected += 1
            print(f"REJECTED: {record.get('patient_id')} - {reason}")

print("\n--- Validation Summary ---")
print(f"Total records: {total}")
print(f"Valid records: {valid}")
print(f"Rejected records: {rejected}")






