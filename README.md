# RoadCare – Public Road Maintenance Priority Analytics System

A beginner-friendly MCA mini-project starter with four integrated modules:
1. Citizen Portal – registration, login, road complaint submission and tracking.
2. Government Admin Portal – review complaints, verify reports and update repair status.
3. Road Condition Analytics – complaint counts, area/severity analysis and charts.
4. Intelligent Repair Priority – transparent priority scoring using severity, traffic, accident history and repeated reports.

## Technology
- Frontend: HTML, CSS, JavaScript, Chart.js
- Backend: Python Flask
- Database: SQLite
- Analytics: Pandas
- No XAMPP required.

## Requirements
- Windows 10/11
- Python 3.10 or newer
- VS Code (recommended)

## Run the project (Windows)

1. Extract `RoadCare.zip`.
2. Open the extracted `RoadCare` folder in VS Code.
3. Open Terminal → New Terminal.
4. Move into the backend folder:
   ```powershell
   cd backend
   ```
5. Create a virtual environment:
   ```powershell
   python -m venv venv
   ```
6. Install packages:
   ```powershell
   python -m pip install -r requirements.txt
   ```
7. Start the application:
   ```powershell
   python app.py
   ```
8. Open this address in your browser:
   http://127.0.0.1:5000

### If PowerShell blocks virtual-environment activation
You do NOT need to activate it. Use:
```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe app.py
```
Or continue with the regular `python` commands if they work.

## Default administrator account
- Email: `admin@roadcare.local`
- Password: `RoadCare@123`

Change this password before using the project beyond a local demonstration. The starter creates this admin account automatically on first run.

## How to test
1. Open the website and register a citizen account.
2. Log in as a citizen and submit a road complaint.
3. Log out.
4. Log in with the administrator account above.
5. Open the Admin Portal, review a complaint and change its status.
6. Open Analytics to see charts and priority recommendations.

## Important project notes
- This is a college-project prototype, not an official government service.
- Use fictional/sample accident and traffic values for demonstration unless you obtain reliable, authorised datasets. The form labels these as reported estimates.
- A priority score is only a decision-support aid. It does not make an official repair decision.
- Uploaded images are stored locally in `backend/uploads`.
- The SQLite database is created automatically at `backend/roadcare.db`.
- The app is configured for local development (`debug=True`). Do not expose it publicly without security review, production configuration, HTTPS, access controls and privacy safeguards.

## Folder structure
```text
RoadCare/
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
└── backend/
    ├── app.py
    ├── analytics.py
    ├── requirements.txt
    └── uploads/
```
