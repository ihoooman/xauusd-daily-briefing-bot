# Contributing

Thanks for considering a contribution.

## Development Setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill only the API keys you need for the area you are testing.

## Local Checks

Before opening a pull request, run:

```bash
python -m py_compile main.py config.py scheduler.py analysis/*.py data_sources/*.py services/*.py utils/*.py
python main.py
```

If you do not have live API keys, make sure the bot fails gracefully and writes clear unavailable-section notes.

## Pull Request Guidelines

- Keep changes focused.
- Do not commit `.env`, generated reports, logs, virtual environments, or caches.
- Do not add fabricated market data, hardcoded prices, hardcoded news, fake odds, or fake technical levels.
- Redact credentials in logs, screenshots, and issue descriptions.
- Update the README when behavior, setup, or required secrets change.

## Data Source Rules

New data providers should:

- Fetch live or near-live data at runtime.
- Surface source names clearly in the report.
- Fail without crashing the whole report.
- Never replace missing data with fake data.

## Trading Disclaimer

This project produces analytical briefings. It must not present output as guaranteed financial advice or a certain buy/sell signal.
