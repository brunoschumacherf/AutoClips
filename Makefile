.PHONY: install up down migrate superuser worker test check
install:
	python -m pip install -r requirements.lock -e '.[test]'
up:
	test -f .env || cp .env.example .env
	docker compose up --build -d
down:
	docker compose down
migrate:
	docker compose run --rm setup
superuser:
	docker compose exec web python manage.py createsuperuser
worker:
	docker compose logs -f worker
test:
	python -m pytest
check:
	python manage.py check
	python manage.py makemigrations --check --dry-run
