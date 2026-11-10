import json
import re
from datetime import datetime, date, timezone

import functions_framework
from google.cloud import storage
from google.cloud import bigquery


# GCP configuration
PROJECT_ID = "project-46c5290c-f673-44aa-941"
DATASET_ID = "healthcare_db"

VALID_TABLE = "clinical_cancer_patients"
REJECTED_TABLE = "clinical_rejected_records"
AUDIT_TABLE = "clinical_ingestion_audit"

storage_client = storage.Client()
bigquery_client = bigquery.Client(project=PROJECT_ID)


# ICD-10 cancer diagnosis code pattern: C00 to C97
CANCER_CODE_PATTERN = re.compile(
    r"^C(0[0-9]|[1-8][0-9]|9[0-7])(\.\d{1,4})?$"
)


def get_table_id(table_name):
    return f"{PROJECT_ID}.{DATASET_ID}.{table_name}"


def is_valid_cancer_code(code):
    if not isinstance(code, str):
        return False

    return bool(CANCER_CODE_PATTERN.fullmatch(code.strip()))


def is_valid_date(date_value):
    if not isinstance(date_value, str):
        return False

    try:
        parsed_date = datetime.strptime(date_value, "%Y-%m-%d")
        return parsed_date.strftime("%Y-%m-%d") == date_value
    except ValueError:
        return False


def validate_record(record):
    """
    Validate one clinical patient record.
    Returns None if valid, otherwise a rejection reason.
    """

    if not isinstance(record, dict):
        return "Record must be a JSON object"

    # Check mandatory fields
    mandatory_fields = [
        "patient_id",
        "hospital_id",
        "diagnosis_code"
    ]

    for field in mandatory_fields:
        value = record.get(field)

        if not isinstance(value, str) or not value.strip():
            return f"Missing or invalid mandatory field: {field}"

    # Check diagnosis date
    if not is_valid_date(record.get("diagnosis_date")):
        return "Invalid diagnosis_date format; expected YYYY-MM-DD"

    # Check cancer diagnosis code
    if not is_valid_cancer_code(record.get("diagnosis_code")):
        return "Non-cancer or invalid diagnosis_code"

    # Check optional fields
    for field in ["disease", "treatment", "doctor"]:
        value = record.get(field)

        if value is not None and not isinstance(value, str):
            return f"Invalid data type for field: {field}"

    return None


def read_gcs_file(bucket_name, file_name):
    """
    Download and read a newline-delimited JSON file from GCS.
    Each line represents one patient record.
    """

    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(file_name)

    file_content = blob.download_as_text(encoding="utf-8")

    records = []
    file_errors = []

    for line_number, line in enumerate(file_content.splitlines(), start=1):
        if not line.strip():
            continue

        try:
            record = json.loads(line)
            records.append(record)

        except json.JSONDecodeError as error:
            file_errors.append({
                "line_number": line_number,
                "raw_record": {"raw_line": line},
                "reason": f"Invalid JSON: {str(error)}"
            })

    return records, file_errors



def find_existing_patient_ids(patient_ids):
    """
    Find patient IDs that already exist in BigQuery.
    """

    if not patient_ids:
        return set()

    query = f"""
        SELECT patient_id
        FROM `{get_table_id(VALID_TABLE)}`
        WHERE patient_id IN UNNEST(@patient_ids)
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ArrayQueryParameter(
                "patient_ids", "STRING", patient_ids
            )
        ]
    )

    query_job = bigquery_client.query(
        query,
        job_config=job_config
    )

    return {row.patient_id for row in query_job.result()}

def is_file_already_processed(file_name):
    query = f"""
        SELECT COUNT(*) AS processed_count
        FROM `{get_table_id(AUDIT_TABLE)}`
        WHERE file_name = @file_name
          AND processing_status = 'SUCCESS'
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter(
                "file_name", "STRING", file_name
            )
        ]
    )

    result = bigquery_client.query(
        query,
        job_config=job_config
    ).result()

    row = next(iter(result))

    return row.processed_count > 0




def insert_valid_records(records, source_file):
    if not records:
        return

    rows = []

    for record in records:
        rows.append({
            "patient_id": record["patient_id"],
            "hospital_id": record["hospital_id"],
            "diagnosis_code": record["diagnosis_code"],
            "disease": record.get("disease"),
            "diagnosis_date": record["diagnosis_date"],
            "treatment": record.get("treatment"),
            "doctor": record.get("doctor"),
            "source_file": source_file,
            "ingestion_timestamp": datetime.now(timezone.utc).isoformat()
        })

    errors = bigquery_client.insert_rows_json(
        get_table_id(VALID_TABLE),
        rows
    )

    if errors:
        raise RuntimeError(f"BigQuery valid-record insertion failed: {errors}")


def insert_rejected_records(records, source_file):
    if not records:
        return

    rows = []

    for item in records:
        rows.append({
            "patient_id": (
			item["record"].get("patient_id")
			if isinstance(item["record"], dict)
			else None
			),
            "source_file": source_file,
            "raw_record": json.dumps(item["record"]),
            "rejection_reason": item["reason"],
            "rejected_timestamp": datetime.now(timezone.utc).isoformat()
        })

    errors = bigquery_client.insert_rows_json(
        get_table_id(REJECTED_TABLE),
        rows
    )

    if errors:
        raise RuntimeError(f"BigQuery rejected-record insertion failed: {errors}")




def insert_audit_record(
    file_name,
    total_records,
    valid_records,
    rejected_records,
    status
):
    row = {
        "file_name": file_name,
        "total_records": total_records,
        "valid_records": valid_records,
        "rejected_records": rejected_records,
        "processing_status": status,
        "processed_timestamp": datetime.now(timezone.utc).isoformat()
    }

    errors = bigquery_client.insert_rows_json(
        get_table_id(AUDIT_TABLE),
        [row]
    )

    if errors:
        raise RuntimeError(f"BigQuery audit insertion failed: {errors}")


@functions_framework.cloud_event
def process_clinical_file(cloud_event):
    """
    Triggered automatically when a new file is uploaded to GCS.
    """

    event_data = cloud_event.data

    bucket_name = event_data["bucket"]
    file_name = event_data["name"]

    # Process only files uploaded into the raw folder
    if not file_name.startswith("raw/"):
        print (f"Skipping file outside raw folder: {file_name}")
        return

    print(f"Processing file: {file_name}")

    if is_file_already_processed(file_name):
        print (f"File already processed. Skipping: {file_name}")
        return

    # Read records from GCS
    records, file_errors = read_gcs_file(
        bucket_name,
        file_name
    )

    valid_records = []
    rejected_records = []

    # Add malformed JSON records to rejected records
    for error in file_errors:
        rejected_records.append({
            "record": error["raw_record"],
            "reason": error["reason"]
        })

    # Validate individual records
    for record in records:
        reason = validate_record(record)

        if reason:
            rejected_records.append({
                "record": record,
                "reason": reason
            })
        else:
            valid_records.append(record)

    # Detect duplicate IDs within the current file
    seen_patient_ids = set()
    unique_records = []

    for record in valid_records:
        patient_id = record["patient_id"]

        if patient_id in seen_patient_ids:
            rejected_records.append({
                "record": record,
                "reason": "Duplicate patient_id within the same file"
            })
        else:
            seen_patient_ids.add(patient_id)
            unique_records.append(record)

    # Detect IDs already present in BigQuery
    existing_ids = find_existing_patient_ids(
        [record["patient_id"] for record in unique_records]
    )

    final_valid_records = []

    for record in unique_records:
        if record["patient_id"] in existing_ids:
            rejected_records.append({
                "record": record,
                "reason": "Duplicate patient_id already exists in BigQuery"
            })
        else:
            final_valid_records.append(record)

    # Insert valid and rejected records
    insert_valid_records(final_valid_records, file_name)
    insert_rejected_records(rejected_records, file_name)

    # Write ingestion audit information
    total_records = len(records) + len(file_errors)

    insert_audit_record(
        file_name,
        total_records,
        len(final_valid_records),
        len(rejected_records),
        "SUCCESS"
    )

    print(f"File processing completed: {file_name}")
    print(f"Total records: {total_records}")
    print(f"Valid records: {len(final_valid_records)}")
    print(f"Rejected records: {len(rejected_records)}")
















































































