# MeetingMind — AI Meeting Intelligence for Notion

> Turn any meeting transcript or audio into structured Notion pages. Automatically.

Built for the [Notion MCP Challenge](https://dev.to/challenges/notion-2026-03-04) on Dev.to.

## The Problem

After building AI systems for a restaurant chain with 236 employees across 14 locations, I found the #1 productivity killer: **meetings where nobody remembered what was decided**.

Action items got lost. Decisions weren't documented. People left meetings with different understanding of what was agreed.

MeetingMind solves this completely. One command, and your meeting is in Notion — structured, searchable, actionable.

## What It Does

```
Meeting transcript or audio
         ↓
   Claude Haiku extracts:
   • Action items (with assignees + due dates)
   • Decisions made (with context + owner)
   • Key topics
   • Blockers
   • Participants
   • Meeting summary
         ↓
   Notion MCP creates structured page
         ↓
   Ready in Notion in ~3 seconds
```

## Demo

```bash
# From transcript file
python meetingmind.py --transcript meeting.txt --notion-db YOUR_DB_ID

# From audio (requires openai-whisper)
python meetingmind.py --audio standup.mp3 --notion-db YOUR_DB_ID

# Dry run (extract only, no Notion write)
python meetingmind.py --dry-run --transcript example_transcript.txt --notion-db x
```

**Output example (dry run with included example):**

```
Extracting meeting intelligence...

Extracted:
  Title       : Team Standup - RAG Refactor & Migration Decision
  Date        : 2026-03-24
  Participants: 3
  Action Items: 6
  Decisions   : 3
  Blockers    : 0
  Sentiment   : positive
```

## Setup

**1. Install Python dependencies**
```bash
pip install -r requirements.txt
```

**2. Install Notion MCP** (requires Node.js 18+)
```bash
npm install -g @notionhq/notion-mcp-server
```

**3. Create a Notion integration**
- Go to https://www.notion.so/my-integrations
- Create integration → copy the token

**4. Create a Notion database** with these properties:
- `Name` (Title)
- `Date` (Date)
- `Participants` (Multi-select)
- `Topics` (Multi-select)
- `Sentiment` (Select: Positive, Neutral, Negative, Mixed)
- `Action Items` (Number)
- `Decisions` (Number)

**5. Configure environment**
```bash
cp .env.example .env
# Edit .env with your keys
```

**6. Run**
```bash
python meetingmind.py --transcript meeting.txt --notion-db YOUR_DATABASE_ID
```

## Why Notion MCP?

The Notion MCP server handles all the heavy lifting:
- Authentication
- API versioning
- Retry logic
- Schema validation

My code focuses on the intelligence layer (extraction) and the integration glue. This is how MCP is supposed to be used — as infrastructure you don't have to maintain.

## Real-World Usage

This tool is based on a system I built for a restaurant chain with 236 employees. Their shift managers leave voice notes at 11pm. The next manager arrives at 6am needing action items.

With this system: voice note → Whisper transcription → MeetingMind extraction → Notion page. In under 10 seconds. Nobody misses a follow-up.

## Cost

Running on Claude Haiku via OpenRouter:
- ~$0.001 per meeting extraction (1000 meetings = ~$1)
- Much cheaper than any meeting note SaaS

## Tech Stack

- Python 3.11+
- OpenRouter API (Claude Haiku for extraction)
- Official Notion MCP Server (`@notionhq/notion-mcp-server`)
- Whisper (optional, local transcription)

## License

MIT — use it, fork it, build on it.

---

Built by [Alessandro Trimarco](https://dev.to/ale_santini_c2c79b33a953a) for the Notion MCP Challenge.
