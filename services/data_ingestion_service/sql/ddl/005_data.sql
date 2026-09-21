CREATE
OR
REPLACE
TABLE feature_snapshot (
    record_id STRING PRIMARY KEY,
    week INT NOT NULL,
    score_date DATE NOT NULL,
    accountweeks FLOAT,
    contractrenewal INT,
    dataplan INT,
    datausage FLOAT,
    custservcalls FLOAT,
    daymins FLOAT,
    daycalls FLOAT,
    monthlycharge FLOAT,
    overagefee FLOAT,
    roammins FLOAT
);