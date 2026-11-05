-- A demo visitor's own settings for the current transaction only (app/demo/overrides.py):
-- set_config's third argument, true, makes each value end with this transaction, so it
-- cannot reach the next request on the same pooled connection. '' means "not set"
-- (app.demo_setting turns it into NULL). Run straight on the driver connection, so its
-- placeholders are psycopg's named style, not SQLAlchemy's colon style. (No percent
-- signs in these comments: psycopg would read them as placeholders too.)
SELECT
    set_config('demo.calorie_budget', %(calorie_budget)s, true),
    set_config('demo.protein_goal', %(protein_goal)s, true),
    set_config('demo.weight_goal_kg', %(weight_goal_kg)s, true),
    set_config('demo.weight_unit', %(weight_unit)s, true),
    set_config('demo.lenient_weekends', %(lenient_weekends)s, true),
    set_config('demo.nickname', %(nickname)s, true)
