-- Runs once, when the Postgres volume is first created.
-- A separate database for automated tests, so tests never touch real data.
CREATE DATABASE snapclass_test;
