#!/bin/sh
# Create the second database the store conformance suite uses.
#
# The suite drops and recreates its tables on every run, so it gets a database of its
# own rather than sharing the one the app writes to. Run once, by the Postgres image's
# entrypoint, on an empty data directory.
set -eu

psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-SQL
	SELECT 'CREATE DATABASE ${POSTGRES_MULTIPLE:-analyst_test}'
	WHERE NOT EXISTS (
	  SELECT FROM pg_database WHERE datname = '${POSTGRES_MULTIPLE:-analyst_test}'
	)\gexec
SQL
