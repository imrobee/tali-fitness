-- Another period sharing at least one day with :start..:end (:id is the one being edited).
SELECT EXISTS (
    SELECT 1 FROM app.vacation
    WHERE id IS DISTINCT FROM CAST(:id AS bigint)
      AND start_date <= :end
      AND end_date >= :start
) AS overlaps;
