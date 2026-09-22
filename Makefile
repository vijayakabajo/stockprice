.PHONY: run migrate makemigrations test lint format shell docker-up docker-down docker-logs

run:
	python manage.py runserver

migrate:
	python manage.py migrate

makemigrations:
	python manage.py makemigrations

test:
	pytest

lint:
	ruff check .
	black --check .

format:
	ruff check --fix .
	black .

shell:
	python manage.py shell

docker-up:
	docker compose up --build

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f
