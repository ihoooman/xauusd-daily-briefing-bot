# XAUUSD Daily Briefing Bot

ربات تحلیل روزانه طلا که هر روز ساعت ۱۲:۰۰ تهران، داده‌های زنده بازار را جمع‌آوری می‌کند و یک گزارش فارسی، خلاصه، حرفه‌ای و معامله‌گرمحور برای XAU/USD می‌سازد.

این پروژه برای سناریوی واقعی ساخته شده است: قیمت زنده، اخبار، تقویم اقتصادی، انتظارات بازار، تحلیل تکنیکال چندتایم‌فریم، جمع‌بندی نهایی و ارسال خودکار به تلگرام. هیچ قیمت، خبر، سطح تکنیکال یا منبعی به‌صورت ساختگی تولید نمی‌شود.

## قابلیت‌ها

- دریافت قیمت زنده XAU/USD از Twelve Data، با fallback نقدی Swissquote
- دریافت اخبار مرتبط با طلا، دلار، فدرال رزرو، تورم، بازدهی اوراق و ریسک ژئوپلیتیک
- تقویم اقتصادی با Financial Modeling Prep و fallback رایگان FRED
- بررسی بازارهای مرتبط Polymarket برای نرخ بهره، تورم، رکود و دلار
- تحلیل تکنیکال تایم‌فریم‌های روزانه، ۴ ساعته و ۱ ساعته
- محاسبه RSI، میانگین‌های متحرک، MACD، حمایت، مقاومت و ساختار قیمت
- خروجی نهایی فقط دوحالته: `LONG / خرید` یا `SHORT / فروش`
- ذخیره گزارش کامل به‌صورت Markdown
- ارسال خلاصه HTML یک‌پیامه به تلگرام طبق Telegram Bot API
- اجرای دستی، اجرای زمان‌بندی‌شده محلی، cron و GitHub Actions

## ساختار پروژه

```text
xauusd-daily-briefing-bot/
├── main.py
├── scheduler.py
├── config.py
├── data_sources/
│   ├── price_data.py
│   ├── news_data.py
│   ├── economic_calendar.py
│   ├── polymarket_data.py
│   └── technical_data.py
├── analysis/
│   ├── fundamental_analysis.py
│   ├── technical_analysis.py
│   └── final_verdict.py
├── services/
│   └── telegram_sender.py
├── utils/
│   ├── logger.py
│   └── time_utils.py
└── output/reports/
```

## نصب

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## تنظیمات محیطی

یک فایل `.env` از روی نمونه بسازید:

```bash
cp .env.example .env
```

کلیدها را فقط در `.env` یا GitHub Secrets قرار دهید. فایل `.env` در git ignore شده و نباید commit شود.

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

## منابع داده

| بخش | منبع اصلی | fallback |
|---|---|---|
| قیمت XAU/USD | Twelve Data | Swissquote public quotes |
| کندل و تکنیکال | Twelve Data | Yahoo Finance `GC=F` به‌عنوان proxy شفاف |
| اخبار | NewsAPI و RSS | پیام عدم دسترسی در گزارش |
| تقویم اقتصادی | Financial Modeling Prep | FRED release dates |
| انتظارات بازار | Polymarket Gamma API | پیام عدم وجود بازار معنادار |

## اجرای دستی

```bash
python main.py
```

گزارش کامل در این مسیر ذخیره می‌شود:

```text
output/reports/xauusd-report-YYYY-MM-DD.md
```

## اجرای روزانه ساعت ۱۲ تهران

```bash
python scheduler.py
```

یا با cron:

```cron
30 8 * * * cd /path/to/xauusd-daily-briefing-bot && /path/to/.venv/bin/python main.py
```

ایران UTC+03:30 است؛ بنابراین ساعت ۱۲ تهران برابر با ۰۸:۳۰ UTC است.

## اجرای GitHub Actions

workflow آماده در مسیر زیر قرار دارد:

```text
.github/workflows/daily-report.yml
```

Secrets لازم در GitHub:

```text
PRICE_API_KEY
NEWS_API_KEY
ECONOMIC_CALENDAR_API_KEY
FRED_API_KEY
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

Variable پیشنهادی:

```text
POLYMARKET_API_URL=https://gamma-api.polymarket.com/markets
```

## تلگرام

اگر `TELEGRAM_BOT_TOKEN` و `TELEGRAM_CHAT_ID` تنظیم باشند، ربات بعد از ذخیره گزارش کامل، یک خلاصه فارسی و HTML-formatted را در یک پیام به تلگرام ارسال می‌کند.

برای جلوگیری از شکستن پیام:

- نسخه Telegram خلاصه‌سازی شده است.
- از `parse_mode=HTML` استفاده می‌شود.
- متن زیر محدودیت ۴۰۹۶ کاراکتری Telegram Bot API نگه داشته می‌شود.
- گزارش کامل همچنان در فایل Markdown ذخیره می‌شود.

## منطق تصمیم نهایی

ربات داده‌های زیر را ترکیب می‌کند:

- اخبار فاندامنتال
- تقویم اقتصادی
- انتظارات Polymarket
- روند و ساختار تکنیکال
- حمایت‌ها و مقاومت‌ها
- وضعیت RSI، MA و MACD

خروجی نهایی فقط یکی از این دو حالت است:

```text
LONG / خرید
SHORT / فروش
```

اگر بازار قطعیت پایینی داشته باشد، ربات همچنان یکی از دو جهت را انتخاب می‌کند، اما سطح اطمینان را `پایین` نشان می‌دهد و در دلیل اصلی، نبود قطعیت را توضیح می‌دهد.

## امنیت

- هیچ API key در کد hardcode نشده است.
- `.env` در `.gitignore` قرار دارد.
- GitHub Actions فقط از Secrets استفاده می‌کند.
- گزارش‌های روزانه تولیدشده به‌صورت پیش‌فرض commit نمی‌شوند.
- خطاهای لاگ‌شده قبل از ذخیره، token و API key را redacted می‌کنند.

## محدودیت‌ها

- FRED برای تقویم اقتصادی، زمان دقیق و forecast ارائه نمی‌دهد؛ فقط تاریخ انتشار رویدادهای اقتصادی را می‌دهد.
- بعضی منابع RSS ممکن است موقتاً در دسترس نباشند.
- اگر API پلن لازم را نداشته باشد، همان بخش با پیام فارسی عدم دسترسی در گزارش ثبت می‌شود.
- این ابزار تحلیل تصمیم‌ساز است، نه سیگنال قطعی معامله.

## نمونه خلاصه تلگرام

```text
گزارش روزانه طلا / XAUUSD
قیمت: 4209.83
سوگیری: LONG / خرید
اطمینان: پایین
حمایت‌ها: 4202.12، 4187.73، 4170.81
مقاومت‌ها: 4215.48، 4215.49، 4216.38
```

## نکته ریسک

«این گزارش صرفاً برای تحلیل و تصمیم‌سازی است و سیگنال قطعی خرید یا فروش محسوب نمی‌شود.»
