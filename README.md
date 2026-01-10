# Pangram GUI

Simple web UI for the Pangram AI detection API.

## Setup

1. Set your API key in `.env`:
   ```
   PANGRAM_API_KEY=your-api-key-here
   ```

2. Run the app:
   ```bash
   uv run main.py
   ```

3. Open http://localhost:5000

## Features

- Paste text and analyze for AI-generated content
- Shows word count and credit usage (1 credit = 1000 words)
- Displays AI/AI-Assisted/Human percentages
- Segment-by-segment analysis with confidence levels
- Highlighted text view showing AI-detected sections
- **History sidebar** - all analyses saved to SQLite database
- **Usage stats** - track total analyses and credits used
- Click any history item to reload without another API call

## Database

All request/response pairs are stored in `pangram_history.db` (SQLite).

Note: The Pangram API doesn't expose usage/billing endpoints, so credit tracking is calculated locally based on word count (1 credit = 1000 words).
