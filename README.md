# RSS to Raindrop.io with LLM Filtering

An intelligent RSS feed processor that filters articles using GPT-4 and saves them to Raindrop.io collections.

## Features

- Processes RSS feeds and filters articles based on configurable criteria
- Uses GPT-4 to analyze article content for intelligent filtering
- Saves articles to Raindrop.io collections
- Maintains state between runs
- Configurable through YAML file
- Handles errors gracefully with retries
- Optional saving of skipped articles for review

## Requirements

- Python 3.8+
- OpenAI API key
- Raindrop.io API token

## Installation

1. Clone the repository:
```bash
git clone https://github.com/fatzombi/rss-to-raindrop-llm.git
cd rss-to-raindrop-llm
```

2. Create and activate a virtual environment using uv:
```bash
uv venv
source .venv/bin/activate  # On Unix/macOS
```

3. Install dependencies:
```bash
uv pip install -r requirements.txt
```

4. Copy `config.example.yaml` to `config.yaml` and update with your settings:
```bash
cp config.example.yaml config.yaml
```

## Configuration

Update `config.yaml` with your settings:
- Add your Raindrop.io API token
- Configure collection IDs for read and skip collections
- Set feed URLs
- Adjust filter criteria as needed

## Usage

Run the script manually:
```bash
python rss_bouncer.py
```

Or set up as a cron job (recommended hourly):
```bash
0 * * * * cd /path/to/rss-to-raindrop-llm && /path/to/python rss_bouncer.py
```

## License

MIT License
