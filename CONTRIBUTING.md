# 👥 Contributing & Setup Guide

Complete guide for collaborators to access databases and work with the DSSC CFRMS system.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Database Access](#database-access)
4. [Development Workflow](#development-workflow)
5. [Testing Requirements](#testing-requirements)
6. [Credentials & Security](#credentials--security)
7. [Common Issues](#common-issues)
8. [Git Workflow](#git-workflow)

---

## Prerequisites

Before you start, ensure you have:

### Required Software

```bash
✓ Git                    # Version control
✓ Python 3.x            # Programming language (3.8+)
✓ Visual Studio Code    # Code editor (recommended)
```

### System Requirements

| Requirement | Minimum |
|---|---|
| **RAM** | 4 GB |
| **Disk** | 2 GB |
| **OS** | Windows 10+ / macOS / Ubuntu |
| **Network** | Stable internet connection |

### Accounts & Access

**Required Access:**

1. **GitHub Account** - Link to repository, branch/PR permissions
2. **Aiven Cloud MySQL** - Credentials from team lead

---

## Environment Setup

### Step 1: Clone Repository

```bash
# Clone the repository
git clone https://github.com/your-org/dssc-cfrms.git
cd dssc-cfrms

# Verify clone
ls -la
# Should show: accounts/, facilities/, reservations/, analytics/, config/, requirements.txt, README.md
```

### Step 2: Create Virtual Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate it (Windows)
.venv\Scripts\activate

# Activate it (macOS/Linux)
source .venv/bin/activate

# Verify activation (should show (.venv) prefix in terminal)
```

### Step 3: Install Dependencies

```bash
# Install all required packages
pip install -r requirements.txt

# Verify installation
python -m django --version
# Should show: 5.1.15
```

### Step 4: Configure Environment Variables

```bash
# Copy template
cp .env.example .env

# Open .env and fill in credentials
# You'll need:
```

**`.env` Configuration:**

```env
# REQUIRED - Development
DEBUG=True
SECRET_KEY=your-django-secret-key-here
ALLOWED_HOSTS=127.0.0.1,localhost

# REQUIRED - Local MySQL Database
DB_NAME=dssc_cfrms_db
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_HOST=127.0.0.1
DB_PORT=3306

# OPTIONAL - Aiven Analytics (only needed for Power BI testing)
ANALYTICS_DB_NAME=dssc_analytics
ANALYTICS_DB_USER=avnadmin
ANALYTICS_DB_PASSWORD=aiven_password_from_team_lead
ANALYTICS_DB_HOST=mysql-xxxx.i.aivencloud.com
ANALYTICS_DB_PORT=16332
ANALYTICS_DB_SSL_CA=C:/path/to/ca.pem
```

**Getting Credentials:**

| Credential | Source | Notes |
|---|---|---|
| `DB_PASSWORD` | Your local MySQL | Set during MySQL installation |
| `ANALYTICS_DB_*` | Team lead/project manager | Request access, provided on-demand |
| `ANALYTICS_DB_SSL_CA` | Download from Aiven | Only needed for Power BI work |

### Step 5: Configure Cloud Database Connection

```bash
# The system now uses Aiven Cloud MySQL for all data
# No local MySQL setup needed!

# Verify your .env has Aiven credentials:
cat .env | grep ANALYTICS_DB

# Should show:
# ANALYTICS_DB_NAME=dssc_analytics
# ANALYTICS_DB_HOST=mysql-xxxx.i.aivencloud.com
# ANALYTICS_DB_USER=avnadmin
# ANALYTICS_DB_PASSWORD=***
# ANALYTICS_DB_SSL_CA=/path/to/ca.pem
```

### Step 6: Run Migrations (Cloud Database)

```bash
# Apply migrations to Aiven cloud database
python manage.py migrate --database=analytics

# Output should show:
# Running migrations for 'analytics'...
# Applying auth.0001_initial...
# Applying accounts.0001_initial...
# etc.

# Verify migrations
python manage.py showmigrations --database=analytics
# Should show checkmarks next to all migrations
```

### Step 7: Create Django Superuser

```bash
# Create admin account (you'll be prompted for username, email, password)
python manage.py createsuperuser

# Enter your credentials:
# Username: your_username
# Email: your_email@example.com
# Password: strong_password_here
# Password (confirm): strong_password_here
```

### Step 8: Generate Test Data

```bash
# Create synthetic test data (required for analytics testing)
python manage.py generate_synthetic_data \
  --facilities 20 \
  --users 50 \
  --reservations 5000

# Output:
# Creating 20 facilities...
# Creating 50 users...
# Creating 5000 reservations...
# Successfully generated synthetic data
```

### Step 9: Verify Installation

```bash
# Run test server
python manage.py runserver

# Open browser to http://localhost:8000
# You should see the CFRMS homepage

# Login to admin
# URL: http://localhost:8000/admin
# Username: (from Step 7)
# Password: (from Step 7)
```

---

## Database Access

### Local Database

**Connection Details:**

```bash
Host:     127.0.0.1
Port:     3306
Username: root
Database: dssc_cfrms_db
```

**Connection Methods:**

1. **Via Django ORM** (recommended)
   ```python
   from accounts.models import User
   User.objects.all()  # Query in Django shell
   ```

2. **Via MySQL CLI**
   ```bash
   mysql -u root -p dssc_cfrms_db -e "SELECT COUNT(*) FROM accounts_user;"
   ```

3. **Via GUI Tool** (MySQL Workbench, DataGrip, etc.)
   - Host: 127.0.0.1
   - Port: 3306
   - User: root
   - Password: (your password)

### Analytics Database (Aiven)

**Connection Details (provided by team):**

```bash
Host:     mysql-xxxx.i.aivencloud.com
Port:     16332
Username: avnadmin
Database: dssc_analytics
SSL/TLS:  Required (ca.pem certificate)
```

**Access:**

- ⚠️ **READ-ONLY** (no writes allowed)
- 📊 Used for Power BI integration
- 🔒 Requires certificate for TLS connection

**Testing Connection:**

```bash
# Test connection (requires ca.pem)
mysql --host=mysql-xxxx.i.aivencloud.com \
      --port=16332 \
      --user=avnadmin \
      --password \
      --ssl-ca=/path/to/ca.pem \
      dssc_analytics -e "SELECT COUNT(*) FROM reservations_reservation WHERE is_synthetic=TRUE;"

# Should return: ~5000 (number of synthetic reservations)
```

### Database Tables

**Core Tables:**

```sql
accounts_user              # User accounts & roles
facilities_facility        # Facility records
facilities_facilitytype    # Facility categories
reservations_reservation   # Booking records
notifications_notification # User notifications
```

**Schema Info:**

```bash
# View all tables
python manage.py dbshell
> SHOW TABLES;

# View table structure
> DESCRIBE accounts_user;
> DESCRIBE facilities_facility;
> DESCRIBE reservations_reservation;
```

---

## Development Workflow

### 1. Create Feature Branch

```bash
# Update main branch
git pull origin main

# Create feature branch
git checkout -b feature/your-feature-name

# Naming conventions:
# feature/user-authentication
# bugfix/fix-reservation-status
# docs/api-documentation
```

### 2. Make Changes

```bash
# Edit files as needed
code .  # Open in VS Code

# Test changes locally
python manage.py runserver

# Run tests
python manage.py test analytics --keepdb --noinput
```

### 3. Commit Changes

```bash
# Stage changes
git add .

# Commit with clear message
git commit -m "Add user authentication endpoint

- Implement login/logout
- Add session management
- Include error handling"

# Message format:
# - Line 1: Brief summary (50 chars max)
# - Line 2: Blank line
# - Lines 3+: Detailed explanation
```

### 4. Push & Create Pull Request

```bash
# Push to remote
git push origin feature/your-feature-name

# Go to GitHub and create Pull Request
# Include:
# - Description of changes
# - Related issues
# - Testing performed
# - Screenshots (if UI changes)
```

### 5. Code Review

```bash
# Wait for review feedback
# Make requested changes
# Push updates (same branch)
git commit -m "Address review feedback"
git push origin feature/your-feature-name

# Merge when approved
```

---

## Testing Requirements

### Before Submitting Pull Request

```bash
# 1. Run all tests
python manage.py test --keepdb --noinput

# 2. Run specific module
python manage.py test analytics --keepdb --noinput

# 3. Check for N+1 queries
python manage.py shell
> from django.db import connection
> from django.test.utils import CaptureQueriesContext
> with CaptureQueriesContext() as ctx:
>     # Run your code
> print(f"Queries: {len(ctx)}")  # Should be < 5

# 4. Lint code
python -m flake8 .

# 5. Check types (if applicable)
python -m mypy analytics/
```

### Test Requirements

**Must Pass:**

- ✅ All 83 existing tests
- ✅ New tests for new features
- ✅ No N+1 queries
- ✅ Linting (PEP 8)
- ✅ Type checking

**Coverage Minimums:**

- Analytics: 100%
- New features: 80%+
- Bug fixes: Include regression test

### Running Specific Tests

```bash
# Test a single file
python manage.py test analytics.tests.TestKPIs --keepdb --noinput

# Test a specific test case
python manage.py test analytics.tests.TestKPIs.test_reservation_kpis --keepdb --noinput

# Run with verbosity
python manage.py test --verbosity=2 --keepdb --noinput

# Run with coverage report
coverage run --source='.' manage.py test --keepdb --noinput
coverage report
```

---

## Credentials & Security

### ⚠️ Security Rules

**DO:**
- ✅ Store credentials in `.env` (never in code)
- ✅ Use environment variables for secrets
- ✅ Rotate passwords regularly
- ✅ Use strong passwords (12+ chars, mixed case, numbers, symbols)
- ✅ Keep `.env` in `.gitignore`
- ✅ Report security issues privately

**DO NOT:**
- ❌ Commit `.env` to Git
- ❌ Share credentials in Slack/email/chat
- ❌ Use default/weak passwords
- ❌ Hardcode secrets in code
- ❌ Share Aiven certificates publicly
- ❌ Post errors with credentials in issues

### Requesting Credentials

**For Local Database:**
```
You set this up during MySQL installation
If forgotten, reset MySQL root password
```

**For Analytics Database:**
```
1. Send email to: team-lead@example.com
2. Subject: CFRMS Analytics Database Access Request
3. Include:
   - Your name
   - GitHub username
   - What you'll be working on
   
4. You'll receive:
   - ANALYTICS_DB_PASSWORD
   - ANALYTICS_DB_HOST
   - ca.pem file (via secure transfer)
```

### Rotating Credentials

```bash
# If password is compromised:

# 1. Update .env
# Edit .env with new password

# 2. Test connection
python manage.py dbshell

# 3. Notify team lead
# Send email to security contact

# 4. For Aiven: Team lead updates Aiven console
```

---

## Common Issues

### Issue 1: "ModuleNotFoundError: No module named 'django'"

**Solution:**
```bash
# Activate virtual environment
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # macOS/Linux

# Reinstall requirements
pip install -r requirements.txt
```

### Issue 2: "Access denied for user 'root'@'localhost'"

**Solution:**
```bash
# Verify MySQL credentials in .env
DB_USER=root
DB_PASSWORD=your_actual_password

# Test MySQL connection
mysql -u root -p -e "SELECT 1;"

# If forgotten, reset MySQL:
# Windows: Use MySQL Installer
# macOS: brew services stop mysql && brew services start mysql
# Linux: sudo /etc/init.d/mysql restart
```

### Issue 3: "No such table: accounts_user"

**Solution:**
```bash
# Run migrations
python manage.py migrate

# Verify migrations ran
python manage.py showmigrations

# If still failing:
python manage.py migrate --run-syncdb
```

### Issue 4: "Database already exists"

**Solution:**
```bash
# Drop and recreate database
mysql -u root -p -e "DROP DATABASE dssc_cfrms_db;"
mysql -u root -p -e "CREATE DATABASE dssc_cfrms_db CHARACTER SET utf8mb4;"

# Rerun migrations
python manage.py migrate
```

### Issue 5: "Test database exists, delete it?" (Tests hanging)

**Solution:**
```bash
# Run with --keepdb flag
python manage.py test --keepdb --noinput

# Or manually delete
mysql -u root -p -e "DROP DATABASE IF EXISTS test_dssc_cfrms_db;"

# Then run tests
python manage.py test --keepdb --noinput
```

### Issue 6: "Aiven connection timeout"

**Solution:**
```bash
# 1. Verify certificate path
ls -la $ANALYTICS_DB_SSL_CA

# 2. Test connection with MySQL CLI
mysql --host=mysql-xxxx.i.aivencloud.com \
      --user=avnadmin \
      --password \
      --ssl-ca=/path/to/ca.pem \
      dssc_analytics -e "SELECT 1;"

# 3. Check network (firewall, VPN)
ping mysql-xxxx.i.aivencloud.com

# 4. Verify Aiven service is running
# Check Aiven console for service status
```

---

## Git Workflow

### Branch Naming Conventions

```
feature/description           # New features
bugfix/description            # Bug fixes
docs/description              # Documentation
refactor/description          # Code refactoring
test/description              # Test improvements
```

### Examples

```bash
git checkout -b feature/add-demand-forecast
git checkout -b bugfix/fix-approval-rate-calc
git checkout -b docs/api-setup-guide
git checkout -b refactor/optimize-kpi-queries
git checkout -b test/add-forecast-tests
```

### Commit Message Format

```
[TYPE] Brief summary (50 chars max)

Detailed explanation of what changed and why.
Include:
- What was changed
- Why it was changed
- Any side effects

Related: #123  # Issue number
```

### Example Commits

```bash
git commit -m "[feature] Add demand forecasting API

- Implement seasonal naive algorithm
- Add exponential smoothing fallback
- Include 4-week forecast endpoint
- Add comprehensive tests

Related: #45"
```

### Pull Request Checklist

Before submitting a PR:

- [ ] Branch is up to date with main
- [ ] All tests pass (`python manage.py test --keepdb --noinput`)
- [ ] Code follows PEP 8 style
- [ ] Docstrings added for all functions
- [ ] No credentials in code or commits
- [ ] `.env` is NOT committed
- [ ] PR description is clear
- [ ] Related issues are referenced

---

## Quick Reference: Day 1 Setup

Copy-paste this to get started in 15 minutes:

```bash
# 1. Clone
git clone https://github.com/your-org/dssc-cfrms.git
cd dssc-cfrms

# 2. Environment
python -m venv .venv
.venv\Scripts\activate

# 3. Install
pip install -r requirements.txt

# 4. Configure
cp .env.example .env
# Edit .env with your MySQL password

# 5. Database
mysql -u root -p -e "CREATE DATABASE dssc_cfrms_db CHARACTER SET utf8mb4;"
python manage.py migrate

# 6. Superuser
python manage.py createsuperuser

# 7. Test data
python manage.py generate_synthetic_data --facilities 20 --users 50 --reservations 5000

# 8. Run
python manage.py runserver

# 9. Access
# http://localhost:8000 (home)
# http://localhost:8000/admin (login with superuser)
```

---

## Quick Reference: Testing

```bash
# All tests
python manage.py test --keepdb --noinput

# Analytics only
python manage.py test analytics --keepdb --noinput

# Specific test
python manage.py test analytics.tests.TestKPIs --keepdb --noinput

# With coverage
coverage run --source='.' manage.py test --keepdb --noinput
coverage report
```

---

## Quick Reference: Git

```bash
# Update from main
git pull origin main

# Create branch
git checkout -b feature/your-feature

# Check status
git status

# Stage changes
git add .

# Commit
git commit -m "[feature] Your change description"

# Push
git push origin feature/your-feature

# Create PR on GitHub
```

---

## Support & Help

### Getting Help

1. **Check Documentation First**
   - README.md
   - CONTRIBUTING.md (this file)
   - Phase completion reports

2. **Search Issues**
   - Look for similar problems
   - Check issue solutions

3. **Ask in Issues**
   - Include error message
   - Steps to reproduce
   - What you've tried

4. **Contact Team Lead**
   - For credential issues
   - For access problems
   - For blocked work

---

## Checklist for Onboarding

Before your first commit, complete:

- [ ] Repository cloned locally
- [ ] Virtual environment created & activated
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] `.env` configured with MySQL credentials
- [ ] Local database created (`CREATE DATABASE dssc_cfrms_db`)
- [ ] Migrations run (`python manage.py migrate`)
- [ ] Superuser created (`python manage.py createsuperuser`)
- [ ] Test data generated (`python manage.py generate_synthetic_data`)
- [ ] Tests pass (`python manage.py test --keepdb --noinput`)
- [ ] Development server runs (`python manage.py runserver`)
- [ ] Can login to admin (`http://localhost:8000/admin`)
- [ ] Feature branch created (`git checkout -b feature/name`)

---

## Version

**Last Updated**: October 12, 2026  
**For**: DSSC CFRMS v6.6.0  
**Questions?** Contact: team-lead@example.com

