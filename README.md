# docker-service-stack

[![CI](https://github.com/w98935977/docker-service-stack/actions/workflows/ci.yml/badge.svg)](https://github.com/w98935977/docker-service-stack/actions/workflows/ci.yml)

**Raspberry Pi 5 / ARM64 實機驗證的 Docker Compose 三層服務架構。**

```text
Client -> Nginx -> FastAPI/Uvicorn -> PostgreSQL
```

這個專案不是單純把三個 container 啟動起來，而是用單機 Docker Compose 實作並驗證：reverse proxy、雙 network 隔離、service health dependency、restart policy、PostgreSQL named volume persistence，以及可驗證的 backup / restore 流程。

## 專案重點

- **Nginx** 作為唯一對外 HTTP entry point，host 僅 publish `8080`。
- **FastAPI / Uvicorn** 同時連接 `frontend` 與 `backend` network，作為唯一 application path。
- **PostgreSQL** 僅位於 `backend` network，不直接暴露 host `5432`。
- 以 healthcheck 實作 `DB healthy -> App healthy -> Nginx` 的 startup sequencing。
- `restart: unless-stopped` 處理 container process exit 後的自動復原。
- `db-data` named volume 保存 PostgreSQL data，container recreate 後資料仍可保留。
- Backup / restore scripts 使用 `pg_dump`、`psql -v ON_ERROR_STOP=1`，避免 restore 失敗後誤報成功。
- GitHub Actions 會實際啟動完整 stack，執行 API、backup、restore 與 post-restore smoke test。

## Raspberry Pi 5 實機驗證

以下項目已在 Raspberry Pi 5 上實際執行：

| 驗證項目 | 結果 |
|---|---|
| Docker Compose build / startup | PASS |
| Nginx -> FastAPI -> PostgreSQL request flow | PASS |
| DB / App / Nginx healthcheck | PASS |
| API write / read | PASS |
| App process crash 後由 restart policy 自動恢復 | PASS |
| PostgreSQL container recreate 後資料保留 | PASS |
| PostgreSQL backup 產生 `.sql.gz` | PASS |

另外，GitHub Actions CI 會驗證 PostgreSQL restore 與 restore 後的 API/data 狀態。

實機測試中也曾發現 Alpine container 內 `localhost` 優先解析為 IPv6 `::1`，造成 Nginx healthcheck 誤判；最後將 self-check 明確改為 `127.0.0.1`。這個修正保留在 Git history / PR 中，可呈現從觀察、定位到修正的 troubleshooting 過程。

## 需求

- Raspberry Pi 5，64-bit Raspberry Pi OS / Ubuntu Server ARM64
- Docker Engine
- Docker Compose v2

## 快速啟動

```bash
cp .env.example .env
# 編輯 .env，設定 POSTGRES_PASSWORD
docker compose config
docker compose up -d --build
./scripts/wait_for_stack.sh
docker compose ps
```

`POSTGRES_PASSWORD` 沒有預設值。若未設定，Compose 會直接拒絕啟動，避免以弱密碼意外部署。

## 整體架構

```text
Client
  |
  | TCP/8080
  v
Nginx
  |
  | frontend network
  v
FastAPI / Uvicorn
  |
  | backend network
  v
PostgreSQL
  |
  v
db-data named volume
```

## 服務說明

| Service | 角色 | Network | Persistence |
|---|---|---|---|
| `nginx` | 對外入口與 reverse proxy | `frontend` | 無 |
| `app` | FastAPI/Uvicorn API | `frontend`, `backend` | 無狀態 |
| `db` | PostgreSQL database | `backend` | `db-data` named volume |

## Network 設計

- `frontend`：只提供 `nginx` 與 `app` 溝通。
- `backend`：只提供 `app` 與 `db` 溝通。
- `db` 不 publish host port，避免不必要的資料庫暴露。
- `app` 同時位於兩個 network，作為 reverse proxy 與 database 之間唯一的 application path。

## Request Flow

```text
curl http://HOST:8080/health
        |
        v
      Nginx
        |
        v
 FastAPI /health
        |
        v
 PostgreSQL SELECT 1
```

FastAPI 的 `/health` 會實際執行 `SELECT 1`，因此 HTTP 200 代表 application process 與 database connection 都可用。

## Startup dependency

Docker Compose 使用 healthcheck 與 `depends_on.condition: service_healthy` 控制啟動順序：

```text
PostgreSQL healthy -> FastAPI /health healthy -> Nginx start
```

這是單機 Compose 的 startup sequencing，不是完整的 service orchestration。

## Healthcheck 與 restart policy

三個 service 都設定：

```yaml
restart: unless-stopped
```

但需要注意：Docker healthcheck 變成 `unhealthy` 並不等於 process exit，因此不一定觸發 restart policy。

例如 PostgreSQL 中斷時：

```text
PostgreSQL unavailable
        |
        v
FastAPI /health -> HTTP 503
        |
        v
app container -> unhealthy
```

此時 Uvicorn process 仍可能存活，所以 Docker 不會只因 health state 為 unhealthy 自動重啟 App。

## Failure scenarios

### PostgreSQL unavailable

- FastAPI `/health` 回傳 HTTP 503。
- App container health state 變為 unhealthy。
- Nginx `/health` 也會因 upstream health endpoint 失敗而失敗。

### FastAPI process exits

- `restart: unless-stopped` 會重新啟動 App container。
- App 恢復前，Nginx 可能暫時回傳 upstream error。

### Nginx process exits

- `restart: unless-stopped` 會重新啟動 Nginx container。

### `docker compose down`

- Containers 與 Compose networks 被移除。
- `db-data` named volume 保留。

### `docker compose down -v`

- Containers、networks 與 `db-data` volume 一併移除。
- PostgreSQL data 會被刪除。

## PostgreSQL persistence

PostgreSQL data 寫入 named volume：

```yaml
volumes:
  - db-data:/var/lib/postgresql/data
```

即使執行 `docker compose down`，只要沒有加 `-v`，資料仍會保留。

## Backup

```bash
./scripts/backup_postgres.sh
```

備份檔輸出到：

```text
backups/service_db-YYYYmmdd-HHMMSS.sql.gz
```

Backup script 直接使用 DB container 內的 `POSTGRES_DB` / `POSTGRES_USER`，不會 `source .env`。Dump 使用 `--clean --if-exists --no-owner --no-privileges`，方便回復到同一個 application database。

## Restore

```bash
./scripts/restore_postgres.sh backups/service_db-YYYYmmdd-HHMMSS.sql.gz
```

或：

```bash
make restore FILE=backups/service_db-YYYYmmdd-HHMMSS.sql.gz
```

Restore 流程：

```text
Confirm
  -> stop Nginx/App
  -> psql -v ON_ERROR_STOP=1
  -> start App/Nginx
  -> wait for /health
```

若 SQL restore 發生錯誤，`psql` 會立即回傳失敗，不會把部分失敗的 restore 誤報為成功。

## 常用指令

```bash
make up
make ps
make health
make logs
make backup
make down
```

或直接使用：

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

## CI

GitHub Actions 會執行：

```text
Compose config validation
-> Python syntax check
-> Bash syntax check
-> docker compose up --build
-> healthcheck smoke test
-> API write/read test
-> PostgreSQL backup
-> PostgreSQL restore
-> post-restore verification
```

## 檔案結構

```text
docker-service-stack/
├── .github/
│   └── workflows/
│       └── ci.yml
├── docker-compose.yml
├── .env.example
├── .gitignore
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
