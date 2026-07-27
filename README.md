# XAUUSD Daily Briefing Bot

[![Daily XAUUSD Persian Briefing](https://github.com/ihoooman/xauusd-daily-briefing-bot/actions/workflows/daily-report.yml/badge.svg)](https://github.com/ihoooman/xauusd-daily-briefing-bot/actions/workflows/daily-report.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

An automated daily Gold / XAUUSD market briefing bot that fetches live market data, builds a professional Persian trading report, saves it as Markdown, and optionally sends a compact HTML-formatted summary to Telegram.

The bot is designed for real daily use. It does not fabricate prices, technical levels, news, economic events, probabilities, or sources. If a data source fails, that section is marked as unavailable instead of being filled with fake data.

## What It Does

- Fetches live or near-live XAU/USD price.
- Pulls fundamental news related to gold, the US dollar, Treasury yields, inflation, the Federal Reserve, jobs data, and geopolitical risk.
- Checks high-impact US macro events through Financial Modeling Prep, with a free FRED fallback.
- Reads relevant Polymarket prediction markets for rate expectations, inflation, recession, dollar strength, and gold-related themes.
- Fetches or derives OHLC data for Daily, 4H, and 1H timeframes.
- Calculates trend, support, resistance, RSI, moving averages, MACD, and recent price structure.
- Produces a Persian Markdown report.
- Sends a one-message Telegram summary using Telegram Bot API HTML formatting.
- Cross-checks the primary spot quote against an independent XAU/USD source.
- Scores source freshness, coverage, consistency, and technical-candle recency before assigning confidence.
- Runs every day at 12:00 Tehran time through GitHub Actions and also supports manual runs.

## Output Language

The codebase and documentation are English. The generated trading report is Persian/Farsi by design.

Final report decisions are intentionally two-way only:

```text
LONG / خرید
SHORT / فروش
```

If market conditions are unclear, the bot still chooses one of the two directions but lowers confidence and explains the uncertainty.

## Project Structure

```text
xauusd-daily-briefing-bot/
├── .github/
│   ├── workflows/daily-report.yml
│   ├── ISSUE_TEMPLATE/
│   └── pull_request_template.md
├── analysis/
│   ├── final_verdict.py
│   ├── fundamental_analysis.py
│   └── technical_analysis.py
├── data_sources/
│   ├── economic_calendar.py
│   ├── news_data.py
│   ├── polymarket_data.py
│   ├── price_data.py
│   └── technical_data.py
├── output/reports/
├── services/telegram_sender.py
├── utils/
├── config.py
├── main.py
├── scheduler.py
├── requirements.txt
└── README.md
```

## Data Sources

| Section | Primary source | Fallback / behavior |
| --- | --- | --- |
| XAU/USD price | Twelve Data | Swissquote public XAU/USD quote |
| Technical candles | Twelve Data XAU/USD | Yahoo Finance `GC=F` as a clearly labeled gold futures proxy |
| News | NewsAPI + verified FXStreet, MarketWatch, and CNBC RSS feeds | Section is marked unavailable if sources fail |
| Economic calendar | Financial Modeling Prep | FRED release dates fallback |
| Prediction markets | Polymarket Gamma API | Section says no meaningful active market was found |
| Telegram delivery | Telegram Bot API | Skipped if credentials are missing |

## Requirements

- Python 3.11+
- API keys for the sources you want to enable
- A Telegram bot token and chat ID if Telegram delivery is needed
- Optional: GitHub repository secrets if running with GitHub Actions

## Installation

```bash
git clone https://github.com/ihoooman/xauusd-daily-briefing-bot.git
cd xauusd-daily-briefing-bot
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Environment Variables

Create a local `.env` file:

```bash
cp .env.example .env
```

Fill only the keys you need:

```env
PRICE_API_KEY=
NEWS_API_KEY=
ECONOMIC_CALENDAR_API_KEY=
FRED_API_KEY=
POLYMARKET_API_URL=https://gamma-api.polymarket.com/markets
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
TIMEZONE=Asia/Tehran
REPORT_TIME=12:00
```

### Variable Reference

| Variable | Required | Purpose |
| --- | --- | --- |
| `PRICE_API_KEY` | Recommended | Twelve Data key for XAU/USD price and OHLC candles |
| `NEWS_API_KEY` | Optional | NewsAPI key for richer fundamental news coverage |
| `ECONOMIC_CALENDAR_API_KEY` | Optional | Financial Modeling Prep calendar key |
| `FRED_API_KEY` | Optional | Free FRED fallback for US economic release dates |
| `POLYMARKET_API_URL` | Optional | Polymarket Gamma API URL |
| `TELEGRAM_BOT_TOKEN` | Optional | Telegram bot token for message delivery |
| `TELEGRAM_CHAT_ID` | Optional | Telegram target chat ID |
| `TIMEZONE` | Optional | Defaults to `Asia/Tehran` |
| `REPORT_TIME` | Optional | Defaults to `12:00` |

Never commit `.env`. It is ignored by git.

## Manual Run

```bash
python main.py
```

Each report is saved here:

```text
output/reports/xauusd-report-YYYY-MM-DD.md
```

## Local Daily Scheduler

```bash
python scheduler.py
```

The default schedule is 12:00 Tehran time.

## Cron Example

12:00 Tehran time is 08:30 UTC while Iran remains UTC+03:30.

```cron
30 8 * * * cd /path/to/xauusd-daily-briefing-bot && /path/to/.venv/bin/python main.py
```

## GitHub Actions Setup

The repository includes:

```text
.github/workflows/daily-report.yml
```

The GitHub Actions workflow runs every day at **12:00 Tehran time** (`08:30 UTC`). You can also trigger it from the Actions tab with **Run workflow** whenever you want an additional fresh report. Manual runs default to `send_telegram=false`; enable the input explicitly only when Telegram delivery is required. Scheduled runs preserve the configured Telegram behavior.

Add these repository secrets:

```text
PRICE_API_KEY
NEWS_API_KEY
ECONOMIC_CALENDAR_API_KEY
FRED_API_KEY
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

Add this repository variable if you want to override the default:

```text
POLYMARKET_API_URL=https://gamma-api.polymarket.com/markets
```

The workflow stores generated Markdown reports as GitHub Actions artifacts. Generated reports are not committed to the repository.

## Telegram Output

The full report is saved as Markdown. Telegram receives a compact, one-message HTML summary to avoid Telegram's 4096-character message limit.

Telegram delivery uses:

```json
{
  "parse_mode": "HTML",
  "disable_web_page_preview": true
}
```

Example summary:

```text
گزارش روزانه طلا / XAUUSD
قیمت: 4209.83
سوگیری: LONG / خرید
اطمینان: پایین
حمایت‌ها: 4202.12، 4187.73، 4170.81
مقاومت‌ها: 4215.48، 4215.49، 4216.38
```

## Decision Model

The final verdict combines:

- Fundamental news sentiment
- Economic calendar risk
- Prediction-market sentiment
- Daily, 4H, and 1H technical trend
- Support and resistance levels
- RSI, moving averages, MACD, and recent price action
- Independent spot-price cross-checking
- Data freshness, source diversity, and completeness scoring

The bot outputs a directional bias, a separately validated trade status, the
current action, confidence, evidence, invalidation criteria, scenarios, and a
risk-management note.

## Evidence and Trade Activation Protocol

Every future report follows these rules:

- `LONG` and `SHORT` are directional **biases**, not active trade signals.
- `Trade Status` is `ACTIVE` only when the latest fully closed 1H candle closes
  beyond the derived trigger and no data-quality blocker exists.
- When the trigger is not confirmed, `Trade Status` is `INACTIVE` and
  `Action now` is `No entry`.
- Open 1H and 4H candles are discarded. Timestamps identify both candle open and
  candle close, and evidence includes the complete OHLC record.
- The observed session range and the latest closed 1H/4H candles are printed
  before any derived technical levels.
- Historical pivots, moving averages, and prediction-market thresholds retain
  explicit origins. They are never described as an observed session touch,
  high, low, or close.
- Touch, break, and close claims require a fully closed candle, an exact
  timestamp, and numerical OHLC evidence.
- Source disagreement, timeframe conflict, or trend/structure contradiction
  lowers confidence and forces `Trade Status` to `INACTIVE`.
- A derived level outside the observed session range is explicitly marked as
  not observed in that session.

## Security

- No API key is hardcoded.
- `.env` is ignored.
- GitHub Actions reads secrets only from GitHub Secrets.
- Generated reports are ignored by default.
- Logged errors are redacted before writing tokens or API keys.
- `.venv`, logs, caches, and generated reports are excluded from git.

If you accidentally expose a key, rotate it immediately in the provider dashboard and update your local `.env` or GitHub Secrets.

## Limitations

- FRED provides economic release dates but not exact event time, forecast, or impact level.
- RSS sources may occasionally fail or change their feed URLs.
- Some APIs may require paid plans for full access.
- Technical levels are calculated only from fetched OHLC data.
- This is an analytical briefing tool, not a guaranteed trading signal.

## Risk Notice

The generated report always includes this Persian risk disclaimer:

```text
«این گزارش صرفاً برای تحلیل و تصمیم‌سازی است و سیگنال قطعی خرید یا فروش محسوب نمی‌شود.»
```

## Contributing

Pull requests are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a PR.

## License

MIT License. See [LICENSE](LICENSE).
