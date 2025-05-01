# Docker Setup for RSO (Rescheduling Test UI)

This document provides instructions for setting up and running the RSO application using Docker and Docker Compose.

## Components

The application consists of three Docker containers:

1. **rso-postgres**: PostgreSQL database
2. **rso-flask**: Flask backend API
3. **rso-react**: React frontend UI

## Docker Container Interactions

The containers interact as follows:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  rso-react  │────▶│  rso-flask  │────▶│rso-postgres │
│  (Frontend) │     │  (Backend)  │     │  (Database) │
└─────────────┘     └─────────────┘     └─────────────┘
      Port 3000           Port 5000           Port 5432
```

- **rso-react** (Frontend) serves the React application on port 3000, making API requests to the backend.
- **rso-flask** (Backend) serves the Flask API on port 5000, handling requests from the frontend and interacting with the database.
- **rso-postgres** (Database) runs PostgreSQL on port 5432, storing all application data.

## Database Configuration

The PostgreSQL container is configured with these settings:

- **Database name**: `RSO`
- **Username**: `postgres`
- **Password**: `root`
- **Host**: Accessible as `rso-postgres` from other containers, or `localhost:5432` from the host machine
- **Schema initialization**: The `src/database/setup.sql` file is automatically executed during first startup

## Prerequisites

- Docker installed on your machine
- Docker Compose installed on your machine

## Setup and Running

### 1. Start the Application

To build and start all containers:

```bash
# Navigate to the project directory
cd /path/to/rso-docker/RSO

# Build and start all containers in detached mode
docker-compose up -d
```

The application will be accessible at:
- Frontend: http://localhost:3000
- Backend API: http://localhost:5000

### 2. View Container Logs

To see logs for all containers:

```bash
docker-compose logs
```

To see logs for a specific container:

```bash
docker-compose logs rso-flask    # For backend logs
docker-compose logs rso-react    # For frontend logs
docker-compose logs rso-postgres # For database logs
```

Add the `-f` flag to follow the logs (continuous output):

```bash
docker-compose logs -f rso-flask
```

### 3. Stop the Application

To stop and remove all containers:

```bash
docker-compose down
```

To stop and remove all containers, including volumes (database data):

```bash
docker-compose down -v
```

### 4. Rebuild Containers

If you make changes to the code, Dockerfiles, or configuration:

```bash
docker-compose up -d --build
```

## Database Inspection and Management

### Connect to the PostgreSQL Container

```bash
# Connect to the PostgreSQL container's shell
docker exec -it rso-postgres bash
```

### Use psql Inside the Container

Once inside the container, connect to the database:

```bash
# Connect to the RSO database as postgres user
psql -U postgres -d RSO

# Alternative format specifying host (same thing inside the container)
psql -h localhost -U postgres -d RSO
```

### Common PostgreSQL Commands

Inside the psql prompt:

```sql
-- List all databases
\l

-- Connect to a specific database
\c RSO

-- List all tables
\dt

-- Show table schema
\d table_name

-- Execute a query
SELECT * FROM tasks LIMIT 10;

-- Exit psql
\q
```

### Using pgAdmin or Other Tools

You can also connect to the database using external tools like pgAdmin, DBeaver, or DataGrip:

- Host: localhost
- Port: 5432
- Username: postgres
- Password: root
- Database: RSO

### Backup and Restore

To backup the database:

```bash
# From the host machine
docker exec -t rso-postgres pg_dump -U postgres -d RSO > backup.sql
```

To restore from a backup:

```bash
# From the host machine
cat backup.sql | docker exec -i rso-postgres psql -U postgres -d RSO
```

## Monitoring Containers

### Check Running Containers

```bash
docker-compose ps
```

### View Resource Usage

```bash
docker stats
```

## Troubleshooting

### Reset Database

If you need to reset the database without rebuilding everything:

```bash
# Stop all containers
docker-compose stop

# Remove only the postgres container and its volume
docker-compose rm -f rso-postgres
docker volume rm rso-docker_postgres_data

# Start all containers again
docker-compose up -d
```

### Inspect Network Configuration

```bash
docker network inspect rso-docker_default
```

### Check Container Environment Variables

```bash
docker exec rso-flask env
```

## Understanding Container Communication

- The Flask backend uses the hostname `rso-postgres` to connect to the PostgreSQL database.
- Environment variables in the Docker Compose file configure the connection settings.
- The React frontend makes API calls to the backend using the URL `http://localhost:5000/api/...`
- Docker's internal DNS resolves the service names to the appropriate container IP addresses.

## Development Workflow

When developing with Docker, you have two main approaches:

1. **Rebuild containers**: Make changes locally, then rebuild and restart containers.
2. **Mount volumes**: Mount local directories as volumes in the containers for real-time code updates.

The current setup uses option 1 for stability. For development, you might want to add volume mounts in docker-compose.yml.