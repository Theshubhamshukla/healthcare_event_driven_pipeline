CREATE TABLE IF NOT EXISTS
`project-46c5290c-f673-44aa-941.healthcare_db.clinical_cancer_patients`
(
  patient_id STRING,
  hospital_id STRING,
  diagnosis_code STRING,
  disease STRING,
  diagnosis_date DATE,
  treatment STRING,
  doctor STRING,
  source_file STRING,
  ingestion_timestamp TIMESTAMP
);

CREATE TABLE IF NOT EXISTS
`project-46c5290c-f673-44aa-941.healthcare_db.clinical_rejected_records`
(
  patient_id STRING,
  source_file STRING,
  raw_record STRING,
  rejection_reason STRING,
  rejected_timestamp TIMESTAMP
);

CREATE TABLE IF NOT EXISTS
`project-46c5290c-f673-44aa-941.healthcare_db.clinical_ingestion_audit`
(
  file_name STRING,
  total_records INT64,
  valid_records INT64,
  rejected_records INT64,
  processing_status STRING,
  processed_timestamp TIMESTAMP
);
