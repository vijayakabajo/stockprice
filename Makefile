.PHONY: run migrate makemigrations apply-sql sql-list check-drift lint format shell

run:
	python manage.py runserver

migrate:
	python manage.py migrate

makemigrations:
	python manage.py makemigrations

# Every model is managed = False: this is what actually builds the schema.
apply-sql:
	python manage.py apply_sql

sql-list:
	python manage.py apply_sql --list

# Unmanaged models emit no DDL, so any output here means a model drifted
# from its .sql file.
check-drift:
	python manage.py makemigrations --check --dry-run

lint:
	ruff check .
	black --check .

format:
	ruff check --fix .
	black .

shell:
	python manage.py shell
