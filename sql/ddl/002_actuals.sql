CREATE
OR
REPLACE
TABLE actuals (
    record_id STRING PRIMARY KEY,
    churn INT NOT NULL,
    known_date DATE NOT NULL
);