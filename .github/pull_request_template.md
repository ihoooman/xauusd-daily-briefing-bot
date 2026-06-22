## Summary

- 

## What changed

- 

## Validation

- [ ] `python -m py_compile main.py config.py scheduler.py analysis/*.py data_sources/*.py services/*.py utils/*.py`
- [ ] `python main.py`

## Data and security checklist

- [ ] No `.env`, logs, generated reports, caches, or virtualenv files are committed.
- [ ] No API keys or Telegram credentials are present in the diff.
- [ ] Missing data sources fail gracefully without fabricated values.
- [ ] README or setup docs are updated if behavior changed.
