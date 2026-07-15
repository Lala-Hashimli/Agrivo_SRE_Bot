.PHONY: install dev test lint format typecheck check docker-build docker-up docker-down

install:
	python -m pip install -r requirements-dev.txt

dev:
	uvicorn app.main:app --reload --port 8085

test:
	pytest

lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy app

check: lint typecheck test
	ruff format --check .

docker-build:
	docker build -t agrivo-sre-bot:local .

docker-up:
	docker compose -f docker-compose.bot.yml up --build

docker-down:
	docker compose -f docker-compose.bot.yml down
