# Rescheduling Test UI (RSO)

A comprehensive UI for testing and visualizing the CP-SAT scheduler and dynamic rescheduling logic.

## Overview

This project provides a visual interface to interact with the scheduling and rescheduling system. It consists of:

1. **Backend**: A Flask API that exposes endpoints to run the scheduler, handle rescheduling events, and retrieve schedule data.
2. **Frontend**: A React application with three main views:
   - Dashboard: View and interact with scheduled tasks
   - Gantt Chart: Visualize tasks on a timeline
   - Calendar: View tasks in a calendar format with resource/employee filtering

## Setup Guide for Beginners

### Prerequisites

- Python 3.7+
- Node.js 14+
- PostgreSQL database (version 12+)
- Git

### Step-by-Step Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/mdriyaz-a/RSO.git
   cd RSO
   ```

2. **Set up the PostgreSQL database**
   - Install PostgreSQL if you haven't already
   - Create a new database using the setup.sql file:
     ```bash
     psql -U postgres -f src/database/setup.sql
     ```
   - If you're using pgAdmin:
     - Open pgAdmin
     - Connect to your PostgreSQL server
     - Open the Query Tool (Tools > Query Tool)
     - Open the setup.sql file and execute it
     
   **Note:** The setup.sql file will:
   - Create a new database named "RSO"
   - Create all necessary sequences
   - Create all tables with proper relationships
   - Insert sample data into all tables
   - Set sequence values to continue after the inserted data

3. **Set up a Python virtual environment (recommended)**
   ```bash
   # For Windows
   python -m venv venv
   venv\Scripts\activate

   # For macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

4. **Install backend dependencies**
   ```bash
   pip install -r requirements.txt
   ```
   
   This will install all the required Python packages including:
   - Flask (Web framework)
   - Flask-CORS (Cross-Origin Resource Sharing support)
   - psycopg2-binary (PostgreSQL adapter)
   - ortools (Google's Operations Research tools for optimization)
   - Other dependencies

5. **Install frontend dependencies**
   ```bash
   cd frontend
   npm install
   cd ..
   ```

## Running the Application

### Option 1: Running Backend and Frontend Separately (Recommended for Beginners)

1. **Start the Backend Server**
   ```bash
   cd src
   python api.py
   ```
   This will start the Flask server on http://localhost:5000

2. **Start the Frontend Development Server** (in a new terminal)
   ```bash
   cd frontend
   npm start
   ```
   This will start the React development server on http://localhost:3000



## Database Configuration

The application is configured to connect to PostgreSQL with these default settings:
- Database name: `RSO`
- Username: `postgres`
- Password: `root`
- Host: `localhost`

If your PostgreSQL setup is different, you'll need to modify the connection settings in `src/api.py`:

```python
conn = psycopg2.connect(
    dbname='rso',
    user='postgres',
    password='root',
    host='localhost'
)
```



## API Endpoints

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|--------------|----------|
| POST | /api/schedule | Run the CP-SAT scheduler | Optional: `{ "start_date": "2025-04-01", "end_date": "2025-05-01" }` | Array of scheduled tasks |
| POST | /api/reschedule/event | Handle a rescheduling event | `{ "task_id": 123, "event_type": "pause\|resume\|complete\|skip\|manual_reschedule", "timestamp": "2025-04-20T14:30:00", "details": {...} }` | Updated schedules and logs |
| GET | /api/schedules | Get all scheduled tasks | - | Array of tasks with schedule details |
| GET | /api/schedules/log | Get recent schedule change logs | - | Object with change_log, pause_log, and combined_logs |
| GET | /api/resources | Get all resources | - | Array of resources |
| GET | /api/employees | Get all employees | - | Array of employees |
| GET | /api/tasks | Get all tasks | - | Array of tasks with dependencies |
| GET | /api/task/:id | Get details for a specific task | - | Task object with dependencies and schedule |

## Demo Scenarios

1. **Initial Schedule**: Click "Run Initial Schedule" on the Dashboard.
2. **Short Break Demo**: Select a task, click the pause button, choose "Short Break", and provide a reason.
3. **End-of-Day Demo**: Start a 4-hour task at 2 PM, simulate a clock-out at 5 PM, and observe the carry-over to the next day.
4. **Overrun + Dependent Shift**: Complete a task later than scheduled and see its dependents pushed forward.
5. **Cross-Project Conflict**: Assign one employee to two tasks in different projects, delay the first, and watch the second auto-delay or reassign based on priority.
6. **Manual Reschedule**: Click a task bar in the Gantt chart, move it earlier or later, provide a reason, and see the chart update.

## Troubleshooting

### Common Issues

1. **Database Connection Error**
   - Verify PostgreSQL is running
   - Check your database credentials in `src/api.py`
   - Make sure the RSO database exists

2. **Missing Dependencies**
   - For backend: `pip install -r requirements.txt` to install all required Python packages
   - For frontend: Make sure you've run `npm install` in the frontend directory

3. **Port Conflicts**
   - If port 5000 is in use, modify the port in `src/api.py`
   - If port 3000 is in use, React will prompt you to use a different port

## Project Structure

```
RSO/
├── src/                    # Backend code
│   ├── api.py              # Flask API
│   ├── main.py             # CP-SAT scheduler
│   ├── rescheduler.py      # Rescheduling logic
│   └── database/           # Database scripts
│       └── setup.sql       # Database schema with tables and sample data
├── frontend/               # React frontend
│   ├── src/
│   │   ├── components/     # Reusable components
│   │   ├── pages/          # Page components
│   │   └── App.js          # Main application
│   └── package.json        # Frontend dependencies
├── requirements.txt        # Python dependencies
├── .gitignore              # Git ignore file
└── README.md               # Project documentation
```

## Pushing Code to GitHub

If you've made changes and want to push them to GitHub, follow these steps:

### First-time Setup

1. **Create a .gitignore file** to exclude node_modules and other unnecessary files:
   ```bash
   # Create .gitignore in the project root
   echo "# Node.js dependencies
   node_modules/
   
   # Build files
   frontend/build/
   
   # Environment variables
   .env
   
   # Python cache files
   __pycache__/
   *.py[cod]
   *$py.class
   
   # IDE files
   .vscode/
   .idea/
   
   # Logs
   *.log
   npm-debug.log*
   
   # OS specific files
   .DS_Store
   Thumbs.db" > .gitignore
   ```

2. **Initialize Git repository** (if not already done):
   ```bash
   git init
   ```

3. **Add the remote repository**:
   ```bash
   git remote add origin https://github.com/mdriyaz-a/RSO.git
   ```

### Pushing Changes

1. **Add your changes**:
   ```bash
   git add .
   ```

2. **Commit your changes**:
   ```bash
   git commit -m "Your commit message here"
   ```

3. **Push to GitHub**:
   ```bash
   git push -u origin main
   ```
   (Use `master` instead of `main` if that's your default branch)

### If You're Updating an Existing Repository

1. **Pull the latest changes first**:
   ```bash
   git pull origin main
   ```

2. **Then add, commit, and push your changes as shown above**
