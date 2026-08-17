# docker-service-stack

Raspberry Pi 5 ARM64 可運行的 Docker Compose 範例：

```text
Client -> Nginx -> FastAPI/Uvicorn -> PostgreSQL
```

## 需求

- Raspberry Pi 5，建議 64-bit Raspberry Pi OS / Ubuntu Server ARM64
- Docker Engine
- Docker Compose v2

## 快速啟動

```bash
cp .env.example .env
# 編輯 .env，至少修改 POSTGRES_PASSWORD
docker compose up -d --build
docker compose ps
curl http://localhost:8080/health
```

## 服務說明

| Service | 角色 | Network | Persistence |
|---|---|---|---|
| `nginx` | 對外入口與 reverse proxy | `frontend` | 無 |
| `app` | FastAPI/Uvicorn API | `frontend`, `backend` | 無狀態 |
| `db` | PostgreSQL database | `backend` | `db-data` named volume |

## Network 設計

- `frontend`：只給 `nginx` 與 `app` 溝通。
- `backend`：只給 `app` 與 `db` 溝通。
- `db` 不對 host 開 port，降低不必要暴露面。

## Startup dependency

Docker Compose 使用 healthcheck 與 `depends_on.condition` 控制基本啟動順序：

```text
PostgreSQL healthy -> FastAPI /health healthy -> Nginx start
```

注意：這不是完整的 service orchestration，只是單機 Compose 環境下的合理啟動保護。

## 資料持久化

PostgreSQL 資料寫入 named volume：

```yaml
volumes:
  - db-data:/var/lib/postgresql/data
```

即使 `docker compose down`，只要沒有執行 `docker compose down -v`，資料仍會保留。

## Backup

```bash
./scripts/backup_postgres.sh
```

備份檔會輸出到：

```text
backups/service_db-YYYYmmdd-HHMMSS.sql.gz
```

## Restore

```bash
./scripts/restore_postgres.sh backups/service_db-YYYYmmdd-HHMMSS.sql.gz
```

或：

```bash
make restore FILE=backups/service_db-YYYYmmdd-HHMMSS.sql.gz
```

## 常用指令

```bash
docker compose up -d --build
docker compose logs -f --tail=100
docker compose ps
docker compose down
```

## 測試 API

```bash
curl http://localhost:8080/
curl http://localhost:8080/health
curl -X POST http://localhost:8080/events/hello-pi5
curl http://localhost:8080/events
```

## 檔案結構

```text
docker-service-stack/
├── docker-compose.yml
├── .env.example
├── README.md
├── Makefile
├── app/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py
├── nginx/
│   └── default.conf
├── scripts/
│   ├── backup_postgres.sh
│   ├── restore_postgres.sh
│   └── wait_for_stack.sh
└── backups/
```
