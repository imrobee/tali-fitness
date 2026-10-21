SELECT day, state, qualifying, island_id, freezes_left
FROM mart.fn_day_status(:today);
