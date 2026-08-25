# Eisenhower Matrix Calendar Planner

A Flask prototype that turns tasks and weekly training preferences into an
Eisenhower-style plan and can create events in Google Calendar.

> **Status:** private prototype undergoing security and structure cleanup. It
> is not currently presented as a flagship portfolio project.

## Security

OAuth credentials, access tokens, refresh tokens, Flask sessions, and local
environment files must never be committed. Configuration is supplied through
environment variables; `.env.example` contains placeholders only.

An OAuth credential was present in an earlier public version of this
repository. That credential must be considered compromised and revoked in
Google Cloud before the integration is used again.

## Local setup

1. Create a virtual environment and install `requirements.txt`.
2. Set `FLASK_SECRET_KEY`, `REDIRECT_URI`, and `GOOGLE_OAUTH_JSON` using the
   placeholders in `.env.example` as a guide.
3. For local HTTP OAuth only, set `OAUTHLIB_INSECURE_TRANSPORT=1` in your shell.
   Never enable it in production.
4. Run `python app.py`.

## Current limitations

- The scheduling logic has not yet been validated with automated tests.
- OAuth sessions are stored on the local filesystem.
- The interface and Python modules still need structural cleanup.
- Production deployment and threat modeling are out of scope for this prototype.
