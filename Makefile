.PHONY: up down logs ps backup restore health

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=100

ps:
	docker compose ps

health:
	curl -fsS http://localhost:8080/health && echo

backup:
	./scripts/backup_postgres.sh

restore:
	@if [ -z "$(FILE)" ]; then echo "Usage: make restore FILE=backups/service_db-YYYYmmdd-HHMMSS.sql.gz"; exit 1; fi
	./scripts/restore_postgres.sh "$(FILE)"
