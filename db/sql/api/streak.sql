SELECT streak, at_risk, freezes_left
FROM mart.fn_streak(:today);
