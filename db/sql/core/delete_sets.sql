-- Re-parse replaces all sets of one activity (inside the same transaction as the insert).
DELETE FROM core.fact_set WHERE activity_key = :activity_key;
