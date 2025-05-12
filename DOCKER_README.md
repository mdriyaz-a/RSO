# Docker Setup for RSO

This guide explains how to run the RSO application using Docker containers.

## Prerequisites

- Docker
- Docker Compose

## Docker Configuration

The application consists of three containerized services:

1. **Frontend** (React): UI for interacting with the scheduler
2. **Backend** (Flask): API endpoints for scheduling operations
3. **Database** (PostgreSQL): Stores all application data

## How to Run

### First-time Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/mdriyaz-a/RSO.git
   cd RSO
   ```

2. Build and start all services:
   ```bash
   docker-compose up --build
   ```

3. Access the application:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:5000

### Subsequent Runs

After the initial setup, you can simply use:
```bash
docker-compose up
```

To run in detached mode (in the background):
```bash
docker-compose up -d
```

To stop all services:
```bash
docker-compose down
```

## Data Persistence

PostgreSQL data is stored in a named Docker volume (`rso-postgres-data`), so your data will persist even if the containers are stopped or removed.

## Accessing Individual Services

### PostgreSQL Database

```bash
docker exec -it rso-db psql -U postgres -d RSO
```

### Backend Container

```bash
docker exec -it rso-backend /bin/bash
```

### Frontend Container

```bash
docker exec -it rso-frontend /bin/sh
```

## Troubleshooting

1. If the backend can't connect to the database, try restarting the backend container:
   ```bash
   docker-compose restart backend
   ```

2. View logs for a specific service:
   ```bash
   docker-compose logs frontend
   docker-compose logs backend
   docker-compose logs db
   ```

3. To completely rebuild everything and start fresh:
   ```bash
   docker-compose down -v
   docker-compose up --build
   ```
