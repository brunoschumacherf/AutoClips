.PHONY: install up down migrate worker test check
install:
	python -m pip install -r requirements.lock -e '.[test]'
up:
	test -f .env || cp .env.example .env
	docker compose up --build -d
down:
	docker compose down
migrate:
	docker compose run --rm setup
worker:
	docker compose logs -f worker
test:
	python -m pytest
check:
	python manage.py check
	python manage.py makemigrations --check --dry-run
