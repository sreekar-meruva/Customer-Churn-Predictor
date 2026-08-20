CREATE
OR
REPLACE
TABLE drift_log (
    week INT NOT NULL,
    feature_name STRING NOT NULL,
    week_mean FLOAT NOT NULL,
    base_mean FLOAT NOT NULL,
    base_std FLOAT NOT NULL,
    drift_score FLOAT NOT NULL,
    computed_at DATETIME NOT NULL,
    PRIMARY KEY (week, feature_name)
)