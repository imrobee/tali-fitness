SELECT format('GRANT CONNECT ON DATABASE %I TO %I', CAST(:database AS text), CAST(:role AS text))
