CREATE
OR
REPLACE
TABLE performance_log (
    week INT NOT NULL,
    model_version STRING NOT NULL,
    num_records INT NOT NULL,
    f2_score FLOAT,
    precision_score FLOAT,
    recall_score FLOAT,
    brier_loss FLOAT,
    brier_threshold FLOAT,
    severity STRING,
    computed_at TIMESTAMP NOT NULL,
    coverage FLOAT,
    batch_count INT,
    not_na_count INT,
    PRIMARY KEY (week, model_version)
)