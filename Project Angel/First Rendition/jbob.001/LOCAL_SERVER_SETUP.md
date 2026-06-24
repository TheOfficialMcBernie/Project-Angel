# Running Task API Server on Your Local Desktop

## Option 1: Docker Compose (RECOMMENDED - Easiest)

This is the simplest way. Just run one command and everything starts.

### Prerequisites
- Docker Desktop installed and running

### Steps

1. **Navigate to your project folder:**
   ```
   cd path\to\your\project
   ```

2. **Start the server:**
   ```
   docker compose up
   ```

   You'll see output like:
   ```
   app_db is already running
   app_web is already running
   ```

3. **Access your API:**
   - **Homepage/Health Check:** http://localhost:5000/health
   - **Admin Login:** http://localhost:5000/auth/login
   - **View Metrics:** http://localhost:5000/metrics
   - **Create Tasks:** http://localhost:5000/api/tasks

4. **Stop the server:**
   ```
   Press Ctrl+C in the terminal
   ```

---

## Option 2: Keep Server Running in Background

If you want the server to keep running even after closing the terminal:

```bash
docker compose up -d
```

Then later, stop it with:
```bash
docker compose down
```

---

## Option 3: Without Docker (Native Python)

If you want to run it directly without containers:

### Prerequisites
- Python 3.11+ installed
- PostgreSQL installed and running

### Steps

1. **Create virtual environment:**
   ```bash
   python -m venv venv
   ```

2. **Activate it:**
   ```bash
   # Windows
   venv\Scripts\activate
   
   # Mac/Linux
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Create .env file:**
   ```bash
   copy .env.example .env
   ```

5. **Set up database (PostgreSQL must be running):**
   ```bash
   python init_db.py
   ```

6. **Start the Flask server:**
   ```bash
   python app.py
   ```

   Or use Gunicorn for production:
   ```bash
   gunicorn --bind 0.0.0.0:5000 app:app
   ```

---

## Quick Test Commands

Once your server is running, try these:

### Health Check
```bash
curl http://localhost:5000/health
```

### Admin Login
```bash
curl -X POST http://localhost:5000/auth/login ^
  -H "Content-Type: application/json" ^
  -d "{\"username\":\"admin\",\"password\":\"admin123\"}"
```

### Create a Task (after login, use the token from above)
```bash
curl -X POST http://localhost:5000/api/tasks ^
  -H "Authorization: Bearer <your_token_here>" ^
  -H "Content-Type: application/json" ^
  -d "{\"title\":\"Learn Docker\",\"description\":\"Complete guide\"}"
```

### View Metrics
```bash
curl http://localhost:5000/metrics
```

---

## Browser Testing (Easier!)

Instead of curl commands, use a tool like **Postman** or **Insomnia**:

1. **Download Postman:** https://www.postman.com/downloads/
2. **Create a request:**
   - Method: POST
   - URL: `http://localhost:5000/auth/login`
   - Body (raw JSON):
     ```json
     {
       "username": "admin",
       "password": "admin123"
     }
     ```
   - Click Send
   - Copy the `access_token` from response

3. **Use the token in next request:**
   - Method: GET
   - URL: `http://localhost:5000/api/admin/users`
   - Headers tab: Add `Authorization` with value `Bearer <your_token>`
   - Click Send

---

## Troubleshooting

### "Port 5000 already in use"
Another app is using port 5000. Either:
- Stop the other app, OR
- Change port: Edit `docker-compose.yml` and change `5000:5000` to `5001:5000`

### "Cannot connect to Docker daemon"
Docker Desktop isn't running:
- Open Docker Desktop application
- Wait for it to start completely
- Try again

### "Database connection error"
PostgreSQL might not be running:
```bash
docker compose down -v
docker compose up
```

### Port 5432 (Database) conflict
```bash
# Kill the process on 5432 (Windows)
netstat -ano | findstr :5432
taskkill /PID <PID> /F

# Or use different port in docker-compose.yml
```

---

## Recommended Setup for Desktop Development

**Option 1 (Simplest - Recommended):**
```bash
docker compose up -d
# Keeps running in background
# Access: http://localhost:5000
# Stop with: docker compose down
```

**Option 2 (If you want to see logs):**
```bash
docker compose up
# Shows live logs
# Stop with: Ctrl+C
```

**Option 3 (Native Python - No Docker):**
```bash
# Requires: Python 3.11, PostgreSQL installed locally
python app.py
# Access: http://localhost:5000
```

---

## Access Points

Once running, you can access:

| Feature | URL |
|---------|-----|
| Health Check | http://localhost:5000/health |
| Admin Login | POST http://localhost:5000/auth/login |
| List Tasks | GET http://localhost:5000/api/tasks |
| Create Task | POST http://localhost:5000/api/tasks |
| View Metrics | http://localhost:5000/metrics |
| Admin Users | GET http://localhost:5000/api/admin/users |
| Audit Logs | GET http://localhost:5000/api/admin/audit-logs |

---

## What's Running

When you start with `docker compose up`:

- **PostgreSQL Database** on port 5432 (internal, you don't need to access it)
- **Flask API Server** on port 5000
- **Admin user** created automatically:
  - Username: `admin`
  - Password: `admin123`

---

## Next Steps

1. **Start the server:** `docker compose up -d`
2. **Test it:** Open http://localhost:5000/health in your browser
3. **Login:** Use Postman to login with admin credentials
4. **Create tasks:** Use the API to create, read, update, delete tasks

That's it! Your local server is ready to use. 🚀

For more details, see `README.md` or `PROJECT_SUMMARY.md`.
