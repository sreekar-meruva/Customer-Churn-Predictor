CREATE
OR
REPLACE
TABLE predictions (
    prediction_id STRING PRIMARY KEY,
    record_id STRING NOT NULL,
    probability FLOAT NOT NULL,
    threshold FLOAT NOT NULL,
    prediction INTEGER NOT NULL,
    week INTEGER NOT NULL,
    score_date DATE NOT NULL,
    score_at DATETIME NOT NULL
);