# Use Docker Compose V2: `docker compose` (plugin), não o binário legado `docker-compose` (Python).
# O v1.29.x costuma quebrar com Docker Engine recente (KeyError: 'ContainerConfig').

.PHONY: up down logs

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f backend

logs-front:
	docker compose logs -f frontend
