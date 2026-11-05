SELECT EXISTS (SELECT 1 FROM pg_database WHERE datname = CAST(:database AS text))
