# Eisenhower Matrix Calendar Planner

A Flask application that turns an Eisenhower matrix into a time-blocked weekly
plan. Tasks are prioritized by quadrant, fitted into free blocks, and written
to the user's primary Google Calendar alongside optional meal and training
blocks.

## Features

- Drag tasks between the four Eisenhower quadrants
- Configure time and repetition rules per quadrant
- Respect existing Google Calendar busy periods
- Add recurring breakfast, lunch, running, and indoor-training blocks
- Report tasks that do not fit within the selected week
- Keep Google OAuth configuration outside source control

## How scheduling works

1. The browser submits tasks, quadrant settings, working hours, and a date range.
2. The Flask API validates the request and obtains the user's free/busy data.
3. `EQ_logic.py` processes quadrants from highest to lowest priority.
4. Events are added only when a sufficiently long free block is available.
5. The API returns a warning when one or more tasks cannot be scheduled.

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a Google OAuth Web application with the Calendar API enabled. Add
`http://localhost:5000/oauth2callback` as an authorized redirect URI, then set
the values described in `.env.example` in your shell or deployment platform.

For local HTTP OAuth only:

```bash
export OAUTHLIB_INSECURE_TRANSPORT=1
python app.py
```

Open `http://localhost:5000`, sign in to Google, add tasks, arrange the matrix,
and select **Schedule this week**.

## Configuration

| Variable | Purpose |
| --- | --- |
| `FLASK_SECRET_KEY` | Signs the Flask session |
| `GOOGLE_OAUTH_JSON` | Complete Google OAuth client JSON, stored as an environment value |
| `REDIRECT_URI` | OAuth callback URL |
| `PORT` | Application port; defaults to `5000` |
| `FLASK_DEBUG` | Enables Flask debug mode only when explicitly set to `1` |

## Tests

```bash
python -m unittest discover -s tests
```

The current suite covers request validation. Calendar insertion should be
tested with a dedicated non-production Google account before deployment.

## Security

Never commit OAuth clients, access tokens, refresh tokens, session files, or
environment files. The repository ignores these paths and reads credentials
from the environment. Production must use HTTPS and must not set
`OAUTHLIB_INSECURE_TRANSPORT`.

## Limitations

- The scheduler currently uses the `Europe/Berlin` timezone.
- Task placement is greedy rather than globally optimized.
- OAuth sessions use Flask's filesystem session backend.
- Calendar event creation is not transactional; a mid-request failure can leave
  some earlier events in place.

## License

Released under the [MIT License](LICENSE).
