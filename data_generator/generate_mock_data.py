import json
import random
from datetime import date, timedelta
from pathlib import Path

OUTPUT_DIR = Path("../sample_data")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

hospitals = ["H001", "H002", "H003"]
doctors = ["Dr. Sharma", "Dr. Patel", "Dr. Kumar"]
treatments = ["Chemotherapy", "Radiation", "Surgery", "Medication"]

def create_record(patient_id, diagnosis_code, disease, diagnosis_date,
                  hospital_id="H001"):
    return {
        "patient_id": patient_id,
        "hospital_id": hospital_id,
        "diagnosis_code": diagnosis_code,
        "disease": disease,
        "diagnosis_date": diagnosis_date,
        "treatment": random.choice(treatments),
        "doctor": random.choice(doctors)
    }

files_data = {
    "clinical_data_2026_11_10.json": [
        create_record("P20001", "C15.3", "Esophageal Cancer", "2026-01-10"),
        create_record("P20002", "C20", "Colorectal Cancer", "2026-02-15"),
        create_record("P20003", "B20.0", "HIV", "2026-03-12"),
    ],

    "clinical_data_2026_11_11.json": [
        create_record("P20004", "C50.9", "Breast Cancer", "2026-04-20"),
        create_record("P20005", "C61", "Prostate Cancer", "2026-05-10"),
        create_record("P20006", "C22.8", "Liver Cancer", "2026/06/15"),
    ],

    "clinical_data_2026_11_12.json": [
        create_record("P20007", "C18.7", "Colon Cancer", "2026-07-10"),
        create_record("P20008", "C16.3", "Stomach Cancer", "2026-08-12"),
        create_record("", "C20", "Colorectal Cancer", "2026-09-15"),
    ],

    "clinical_data_2026_11_13.json": [
        create_record("P20009", "C22.8", "Liver Cancer", "2026-10-10"),
        create_record("P20010", "C50.9", "Breast Cancer", "2026-10-15", ""),
        create_record("P20001", "C15.3", "Esophageal Cancer", "2026-01-10"),
    ]
}

for file_name, records in files_data.items():
    file_path = OUTPUT_DIR / file_name

    with open(file_path, "w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record) + "\n")

    print(f"Generated: {file_path}")

print("All mock data files generated successfully!")
