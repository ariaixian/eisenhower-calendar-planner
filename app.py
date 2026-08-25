import os
import json
import datetime
import random
import secrets

from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from flask_session import Session
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from EQ_logic import schedule_tasks

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY") or secrets.token_hex(32)

REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:5000/oauth2callback")
IS_HTTPS = REDIRECT_URI.startswith("https://")

app.config.update(
    SESSION_TYPE='filesystem',
    SESSION_PERMANENT=True,
    PERMANENT_SESSION_LIFETIME=3600,  # 1 hour
    SESSION_FILE_DIR=os.path.join(os.getcwd(), 'flask_sessions'),
    SESSION_FILE_THRESHOLD=100,
    SESSION_COOKIE_NAME='session',
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=IS_HTTPS,
)

Session(app)


SCOPES = [
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/calendar.readonly'
]

QUADRANTS = {
    "urgent_important",
    "important_not_urgent",
    "not_important_urgent",
    "not_important_not_urgent",
}


def oauth_client_config():
    """Load OAuth configuration from the environment, never the repository."""
    raw_config = os.getenv("GOOGLE_OAUTH_JSON")
    if not raw_config:
        raise RuntimeError("GOOGLE_OAUTH_JSON is required for Google Calendar login")

    config = json.loads(raw_config)
    if not (config.get("web") or config.get("installed")):
        raise RuntimeError("GOOGLE_OAUTH_JSON must contain a web or installed OAuth client")
    return config


def oauth_client_details():
    config = oauth_client_config()
    return config.get("web") or config["installed"]




@app.route('/')
def index():
    logged_in = 'credentials' in session
    return render_template('index.html', logged_in=logged_in)

@app.route('/login')
def login():
    flow = Flow.from_client_config(
        oauth_client_config(),
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
    )
    session['oauth_state'] = state
    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    if request.args.get('state') != session.get('oauth_state'):
        return "State mismatch — possible CSRF attack", 400

    flow = Flow.from_client_config(
        oauth_client_config(),
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )

    flow.fetch_token(authorization_response=request.url)

    credentials = flow.credentials
    session['credentials'] = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'scopes': credentials.scopes
    }

    return redirect(url_for('index'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


@app.route('/generate_workouts')
def generate_workouts():
    runs = int(request.args.get("runs", 2))
    indoor = int(request.args.get("indoor", 2))

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    random.shuffle(days)
    selected = days[:runs + indoor]

    workouts = [{"day": d, "type": "Run"} for d in selected[:runs]] + \
               [{"day": d, "type": "Indoor Training"} for d in selected[runs:runs + indoor]]

    return jsonify({"workouts": workouts})


def generate_workouts_from_date_range(start_str, end_str, runCount, indoorCount):
    start_date = datetime.datetime.strptime(start_str, "%Y-%m-%d").date()
    end_date = datetime.datetime.strptime(end_str, "%Y-%m-%d").date()
    days_range = [(start_date + datetime.timedelta(days=i)).strftime('%A') for i in range((end_date - start_date).days + 1)]

    random.shuffle(days_range)
    run_days = days_range[:runCount]
    indoor_days = days_range[runCount:runCount + indoorCount]

    return [{"type": "🏃 Run", "day": d} for d in run_days] + \
           [{"type": "🏋️ Functional", "day": d} for d in indoor_days]


def validate_schedule_request(data):
    required = {
        "tasks", "weekStart", "weekEnd", "workStart", "workEnd",
        "urgentImportantDays", "urgentImportantHours",
        "importantNotUrgentDays", "importantNotUrgentHours",
        "notImportantUrgentDays", "notImportantUrgentHours",
        "notUrgentNotImportantDays", "notUrgentNotImportantHours",
        "runCount", "indoorCount", "breakfastStart", "breakfastDuration",
        "lunchStart", "lunchDuration",
    }
    if not isinstance(data, dict):
        return "Request body must be a JSON object."
    missing = sorted(required.difference(data))
    if missing:
        return f"Missing required fields: {', '.join(missing)}."

    try:
        start_date = datetime.datetime.strptime(data["weekStart"], "%Y-%m-%d").date()
        end_date = datetime.datetime.strptime(data["weekEnd"], "%Y-%m-%d").date()
        datetime.datetime.strptime(data["workStart"], "%H:%M")
        datetime.datetime.strptime(data["workEnd"], "%H:%M")
        datetime.datetime.strptime(data["breakfastStart"], "%H:%M")
        datetime.datetime.strptime(data["lunchStart"], "%H:%M")
    except (TypeError, ValueError):
        return "Dates and times must use YYYY-MM-DD and HH:MM formats."

    if end_date < start_date or (end_date - start_date).days > 13:
        return "The schedule range must be between 1 and 14 days."
    if data["workEnd"] <= data["workStart"]:
        return "Work end time must be later than work start time."
    if not isinstance(data["tasks"], list) or not data["tasks"]:
        return "Add at least one task before scheduling."
    for task in data["tasks"]:
        if not isinstance(task, dict) or not str(task.get("name", "")).strip():
            return "Every task needs a name."
        if task.get("quadrant") not in QUADRANTS:
            return "Every task must belong to a valid Eisenhower quadrant."

    numeric_fields = required.difference({
        "tasks", "weekStart", "weekEnd", "workStart", "workEnd",
        "breakfastStart", "lunchStart",
    })
    try:
        if any(float(data[field]) < 0 for field in numeric_fields):
            return "Durations and counts cannot be negative."
    except (TypeError, ValueError):
        return "Durations and counts must be numeric."
    return None


def get_free_blocks(service, day, work_start, work_end, tz):
    start_of_day = tz.localize(datetime.datetime.combine(day, datetime.datetime.strptime(work_start, "%H:%M").time()))
    end_of_day = tz.localize(datetime.datetime.combine(day, datetime.datetime.strptime(work_end, "%H:%M").time()))

    response = service.freebusy().query(body={
        "timeMin": start_of_day.isoformat(),
        "timeMax": end_of_day.isoformat(),
        "timeZone": "Europe/Berlin",
        "items": [{"id": "primary"}]
    }).execute()

    busy_times = response['calendars']['primary']['busy']
    free_blocks = []

    last_end = start_of_day
    for event in busy_times:
        busy_start = datetime.datetime.fromisoformat(event['start'])
        busy_end = datetime.datetime.fromisoformat(event['end'])

        if last_end < busy_start:
            free_blocks.append((last_end, busy_start))
        last_end = max(last_end, busy_end)

    if last_end < end_of_day:
        free_blocks.append((last_end, end_of_day))

    return free_blocks


@app.route('/schedule', methods=['POST'])
def schedule():
    if 'credentials' not in session:
        return 'User not logged in', 401

    client = oauth_client_details()
    creds = Credentials(
        **session['credentials'],
        client_id=client['client_id'],
        client_secret=client['client_secret'],
    )
    data = request.get_json(silent=True)
    validation_error = validate_schedule_request(data)
    if validation_error:
        return jsonify({"status": "error", "error": validation_error}), 400

    events, warning = schedule_tasks(
        data["tasks"], creds, data["weekStart"], data["weekEnd"],
        {
            "urgent_important": data["urgentImportantHours"],
            "important_not_urgent": data["importantNotUrgentHours"],
            "not_important_urgent": data["notImportantUrgentHours"],
            "not_important_not_urgent": data["notUrgentNotImportantHours"]
        },
        {
            "urgent_important": data["urgentImportantDays"],
            "important_not_urgent": data["importantNotUrgentDays"],
            "not_important_urgent": data["notImportantUrgentDays"],
            "not_important_not_urgent": data["notUrgentNotImportantDays"]
        },
        data["runCount"], data["indoorCount"],
        data["workStart"], data["workEnd"],
        generate_workouts_from_date_range(
            data["weekStart"],
            data["weekEnd"],
            data["runCount"],
            data["indoorCount"]
        ),
        get_free_blocks,
        data["breakfastStart"], data["breakfastDuration"],
        data["lunchStart"], data["lunchDuration"]
    )

    return jsonify({"status": "success", "warning": warning})


if __name__ == '__main__':
    app.run(
        debug=os.getenv("FLASK_DEBUG") == "1",
        port=int(os.getenv("PORT", "5000")),
    )
