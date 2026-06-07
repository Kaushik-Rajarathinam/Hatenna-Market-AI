# Poketwo Market Intelligence AI

A standalone Discord bot for analyzing historical Poketwo auction data from SQLite.

This project is intentionally separate from the Hatenna bot codebase. Phase 1 focuses on reliable SQL analytics only: market stats, comparable sales, trend analysis, and recent sale lookup.

## Architecture

```text
market_ai/
├── bot.py
├── config.py
├── db.py
├── models.py
├── analytics/
│   ├── filters.py
│   ├── queries.py
│   ├── stats.py
│   ├── comparables.py
│   └── trends.py
├── commands/
│   ├── market.py
│   ├── deal.py
│   ├── trend.py
│   └── predict.py
├── ml/
│   ├── train.py
│   └── predictor.py
└── ai/
    ├── prompts.py
    └── llm.py
```

## Setup

Use Python 3.10.

```bash
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Move your SQLite database to:

```text
data/auctions.db
```

Or point the bot at another location:

```bash
export AUCTIONS_DB_PATH=/path/to/auctions.db
```

Validate the database and create the recommended indexes:

```bash
python -m market_ai.validate_db
```

Set your Discord token:

```bash
export DISCORD_TOKEN=your-token-here
```

Run the bot:

```bash
python -m market_ai.bot
```

## Environment Variables

`DISCORD_TOKEN`: Discord bot token.

`COMMAND_PREFIX`: Optional command prefix. Defaults to `!`.

`AUCTIONS_DB_PATH`: Optional SQLite path. Defaults to `data/auctions.db`.

`OPENAI_API_KEY`: Reserved for Phase 3 LLM explanations.

`OPENAI_MODEL`: Optional model for explanations. Defaults to `gpt-5.4-nano`.

`OPENAI_EXPLANATIONS_ENABLED`: Set to `false` to use local stats/ML explanations without calling OpenAI.

## Database

Expected table: `auctions`

Useful columns include `auction_id`, `price`, `name`, `level`, `shiny`, `gender`, `hp_iv`, `attack_iv`, `defense_iv`, `sp_atk_iv`, `sp_def_iv`, `speed_iv`, `gmax`, `auction_date`, `is_missingno`, and optional `iv`.

If `iv` exists, it is normalized as:

```text
0..1 ratio -> ratio * 100
>100 raw total IV -> raw / 186 * 100
otherwise -> percentage
```

If `iv` does not exist, IV percentage is computed from the six IV columns.

## Commands

```text
!market Garchomp
!market shiny Garchomp
!market Garchomp iv>=90
!market Garchomp shiny iv>=85

!deal Garchomp 91 750000
!deal shiny Garchomp 91 750000

!trend Garchomp
!recent Garchomp
```

## Filters

Supported tokens:

```text
shiny
sh
gmax
gigantamax
missingno
iv>=90
iv<=50
iv=100
price>=100000
price<=500000
level>=50
level<=100
```

Everything else is treated as part of the Pokemon name.

## Example Output

`!market shiny Garchomp iv>=90`

```text
Sample: 128
Median: 1.25M pc
Average: 1.31M pc
Min: 750,000 pc
Max: 2.3M pc
25th / 75th: 980,000 pc / 1.55M pc
Newest: 2026-06-01
Oldest: 2025-03-14
```

`!deal Garchomp 91 750000`

```text
Verdict: Underpriced
Comparable Sales: 42
Median Comparable: 930,000 pc
Vs Median: -19.4%
```

## ML Training

Phase 2 trains a price model and saves:

```text
models/price_model.pkl
models/model_metadata.json
```

Start with a small sample to confirm the pipeline:

```bash
python -m market_ai.ml.train --limit 10000 --strategy recent --estimators 40
```

Then train on the most recent 200k valid auction rows:

```bash
python -m market_ai.ml.train --limit 200000 --strategy recent --estimators 250
```

Use the full database after the recent model looks reasonable:

```bash
python -m market_ai.ml.train --limit 0 --strategy recent --estimators 350
```

To train on a random historical sample instead:

```bash
python -m market_ai.ml.train --limit 100000 --strategy random --estimators 250
```

The feature set includes Pokemon name, level, shiny, gmax, gender, IVs, total IV, IV percent, custom color, XP, and MissingNo status.

Once a model exists, use:

```text
!predict Garchomp 91
!predict shiny Garchomp 91
!predict gmax Charizard 85

!marketai shiny Garchomp 91 750000
!advisor gmax Charizard 85
```

`!marketai` gathers real SQL stats, trend data, recent comparable sales, and the saved ML prediction first. The LLM only explains that summarized payload; it does not query SQLite directly.

## LLM Layer

Phase 3 will add optional OpenAI explanations. The LLM will only receive structured statistics already computed by the app. It will not query SQLite directly.

## Roadmap

- Phase 1: SQL analytics commands
- Phase 2: ML price prediction
- Phase 3: LLM market explanations
- Later: richer filters, slash commands, charts, scheduled market summaries

## Resume Bullet

Built an AI-powered market intelligence Discord bot using 2.3GB+ of historical Poketwo auction data, SQLite analytics, machine-learning price prediction, and LLM-generated market explanations.
