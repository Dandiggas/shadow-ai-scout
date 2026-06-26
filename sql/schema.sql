CREATE TABLE IF NOT EXISTS runs (
  run_id String,
  created_at DateTime,
  company_context String,
  policy_json String,
  requested_tools Array(String)
) ENGINE = MergeTree
ORDER BY (created_at, run_id);

CREATE TABLE IF NOT EXISTS sources (
  run_id String,
  tool_name String,
  source_url String,
  source_title String,
  source_type String,
  fetched_at DateTime,
  content_hash String,
  snippet String
) ENGINE = MergeTree
ORDER BY (run_id, tool_name, source_type, source_url);

CREATE TABLE IF NOT EXISTS risk_claims (
  run_id String,
  tool_name String,
  source_url String,
  source_type String,
  risk_category String,
  claim_text String,
  evidence_quote String,
  severity UInt8,
  confidence Float32,
  extracted_at DateTime
) ENGINE = MergeTree
ORDER BY (run_id, tool_name, risk_category, severity);

CREATE TABLE IF NOT EXISTS verdicts (
  run_id String,
  tool_name String,
  risk_score UInt8,
  verdict String,
  failed_policy Array(String),
  summary String,
  recommended_policy String,
  created_at DateTime
) ENGINE = MergeTree
ORDER BY (run_id, risk_score, tool_name);
