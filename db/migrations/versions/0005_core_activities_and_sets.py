"""Core star schema for activities and lifting sets (ARCHITECTURE.md section 5.2).

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-21
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Strava sport_type -> app_type. Filled from db/seeds/dim_activity_type.csv; sport
    # types not in the CSV are added automatically as 'other'.
    op.execute(
        """
        CREATE TABLE core.dim_activity_type (
            activity_type_key integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            strava_sport_type text    NOT NULL UNIQUE,
            app_type          text    NOT NULL CHECK (app_type IN
                ('run', 'walk', 'cycle', 'swim', 'strength', 'yoga', 'hiit', 'other')),
            label             text    NOT NULL
        )
        """
    )

    # Exercise name -> primary muscle group, from db/seeds/exercise_muscle_map.csv.
    op.execute(
        """
        CREATE TABLE core.exercise_muscle_map (
            exercise_name text PRIMARY KEY,
            muscle_group  text NOT NULL
        )
        """
    )

    # NULLS NOT DISTINCT: "Goblet Squat" with no equipment is one row, not a new row on
    # every re-parse (a plain UNIQUE treats every NULL as different; DECISIONS D6).
    op.execute(
        """
        CREATE TABLE core.dim_exercise (
            exercise_key  integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            exercise_name text    NOT NULL,
            equipment     text,
            muscle_group  text    NOT NULL DEFAULT 'Unmapped',
            CONSTRAINT dim_exercise_name_equipment_key
                UNIQUE NULLS NOT DISTINCT (exercise_name, equipment)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE core.fact_activity (
            activity_key      bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            strava_id         bigint      NOT NULL UNIQUE REFERENCES raw.strava_activities,
            date_key          integer     NOT NULL REFERENCES core.dim_date,
            activity_type_key integer     NOT NULL REFERENCES core.dim_activity_type,
            title             text,
            started_at        timestamptz NOT NULL,   -- from start_date (UTC)
            started_local     timestamp   NOT NULL,   -- wall-clock time where it happened
            ended_at          timestamptz NOT NULL,   -- started_at + elapsed time
            tz                text,                   -- IANA name, e.g. Asia/Manila
            duration_s        integer     NOT NULL CHECK (duration_s >= 0),  -- elapsed_time
            moving_s          integer     CHECK (moving_s >= 0),
            distance_m        numeric     CHECK (distance_m >= 0),
            avg_hr            numeric,
            calories_burned   numeric,
            description_raw   text,
            -- NULL = a Hevy description not parsed yet.
            parse_status      text        CHECK (parse_status IN
                ('ok', 'partial', 'not_hevy', 'not_applicable')),
            source_fetched_at timestamptz NOT NULL,   -- raw row's fetched_at
            -- Which raw version was parsed: re-parse when it differs from
            -- source_fetched_at (an exact match, independent of any clock).
            parsed_fetched_at timestamptz,
            parsed_at         timestamptz,            -- when the parse ran (information)
            parser_version    integer,
            CHECK (
                date_key = (EXTRACT(YEAR FROM started_local) * 10000
                            + EXTRACT(MONTH FROM started_local) * 100
                            + EXTRACT(DAY FROM started_local))::int
            )
        )
        """
    )

    # One row per set. Which measures are filled depends on set_kind (DECISIONS D17);
    # the CHECK below makes the database enforce it.
    op.execute(
        """
        CREATE TABLE core.fact_set (
            set_key        bigint  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            activity_key   bigint  NOT NULL REFERENCES core.fact_activity ON DELETE CASCADE,
            date_key       integer NOT NULL REFERENCES core.dim_date,
            exercise_key   integer NOT NULL REFERENCES core.dim_exercise,
            exercise_order integer NOT NULL CHECK (exercise_order >= 1),
            set_number     integer NOT NULL CHECK (set_number >= 1),
            set_kind       text    NOT NULL CHECK (set_kind IN
                ('weight_reps', 'reps', 'distance_duration', 'duration')),
            weight_kg      numeric CHECK (weight_kg >= 0),
            reps           integer CHECK (reps >= 1),
            distance_m     numeric CHECK (distance_m > 0),
            duration_s     integer CHECK (duration_s > 0),
            orig_weight    numeric,
            orig_unit      text    CHECK (orig_unit IN ('kg', 'lb')),
            exercise_note  text,
            volume_kg      numeric GENERATED ALWAYS AS (
                CASE WHEN set_kind = 'weight_reps' THEN weight_kg * reps ELSE 0 END
            ) STORED,
            UNIQUE (activity_key, exercise_order, set_number),
            CHECK (
                (set_kind = 'weight_reps'
                    AND weight_kg IS NOT NULL AND reps IS NOT NULL
                    AND orig_weight IS NOT NULL AND orig_unit IS NOT NULL
                    AND distance_m IS NULL AND duration_s IS NULL)
                OR (set_kind = 'reps'
                    AND reps IS NOT NULL
                    AND weight_kg IS NULL AND orig_weight IS NULL AND orig_unit IS NULL
                    AND distance_m IS NULL AND duration_s IS NULL)
                OR (set_kind = 'distance_duration'
                    AND distance_m IS NOT NULL AND duration_s IS NOT NULL
                    AND weight_kg IS NULL AND orig_weight IS NULL AND orig_unit IS NULL
                    AND reps IS NULL)
                OR (set_kind = 'duration'
                    AND duration_s IS NOT NULL
                    AND weight_kg IS NULL AND orig_weight IS NULL AND orig_unit IS NULL
                    AND reps IS NULL AND distance_m IS NULL)
            )
        )
        """
    )


def downgrade() -> None:
    raise NotImplementedError("Migrations are forward-only (CLAUDE.md #6).")
