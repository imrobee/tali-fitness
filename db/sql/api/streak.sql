SELECT streak, at_risk, today_state, today_kind, yesterday_kind
FROM mart.fn_streak(:today);
