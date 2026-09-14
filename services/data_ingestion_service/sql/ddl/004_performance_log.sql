CREATE
OR
REPLACE
TABLE performance_log (
    week INT NOT NULL,
    model_version STRING NOT NULL,
    batch_count INT NOT NULL,
    f2_score FLOAT,
    precision_score FLOAT,
    recall_score FLOAT,
    brier_loss FLOAT,
    brier_threshold FLOAT,
    severity STRING,
    computed_at DATE NOT NULL,
    coverage FLOAT,
    not_na_count INT,
    PRIMARY KEY (week, model_version)
)