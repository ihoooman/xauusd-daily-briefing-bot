# Security Policy

## Supported Versions

The `main` branch is the supported version.

## Secrets

This project uses API keys and Telegram credentials. Never commit:

- `.env`
- API keys
- Telegram bot tokens
- Telegram chat IDs
- generated logs containing request URLs
- generated reports that may reveal private operational context

Use GitHub Secrets for CI/CD:

- `PRICE_API_KEY`
- `NEWS_API_KEY`
- `ECONOMIC_CALENDAR_API_KEY`
- `FRED_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

## Reporting a Vulnerability

If you find a security issue, open a private security advisory on GitHub if available, or contact the maintainer directly. Do not post live secrets or exploit details in public issues.

## Accidental Secret Exposure

If a key is exposed:

1. Revoke or rotate it at the provider.
2. Remove it from local files and GitHub Secrets.
3. Check logs and artifacts.
4. Re-run the workflow with the rotated value.
