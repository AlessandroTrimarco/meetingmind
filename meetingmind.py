#!/usr/bin/env python3
"""
MeetingMind -- AI Meeting Intelligence for Notion
Extracts structured data from meeting transcripts and creates Notion pages via MCP.

Usage:
    python meetingmind.py --transcript meeting.txt --notion-db YOUR_DB_ID
    python meetingmind.py --audio meeting.mp3 --notion-db YOUR_DB_ID
    python meetingmind.py --dry-run --transcript meeting.txt --notion-db x
"""

import os, json, argparse, subprocess, sys, urllib.request
from pathlib import Path
from datetime import datetime

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
MODEL = "anthropic/claude-haiku-4-5"

EXTRACTION_PROMPT = """You are extracting structured intelligence from a meeting transcript.
Extract ONLY factual information explicitly stated. Do NOT infer or add context.

Return JSON with this exact structure:
{
  "meeting_title": "Brief descriptive title (max 60 chars)",
  "date": "YYYY-MM-DD or null",
  "participants": [{"name": "string", "role": "string or null"}],
  "summary": "2-3 sentence factual summary",
  "decisions": [
    {"decision": "what was decided", "context": "why (brief)", "owner": "person or null"}
  ],
  "action_items": [
    {"task": "what needs to be done", "assignee": "person or null", "due_date": "YYYY-MM-DD or null", "priority": "high|medium|low"}
  ],
  "key_topics": ["topic1", "topic2"],
  "blockers": ["blocker1"],
  "sentiment": "positive|neutral|negative|mixed"
}

Rules:
- Mark as null anything not explicitly mentioned
- Maximum 10 action items, 5 decisions, 8 topics
- DO NOT add context not present in the transcript

TODAY: {today}

TRANSCRIPT:
{transcript}"""


def load_env():
    env_file = Path(__file__).parent.parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def extract_from_transcript(transcript: str) -> dict:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("Set OPENROUTER_API_KEY in .env")

    today = datetime.now().strftime("%Y-%m-%d")
    prompt = EXTRACTION_PROMPT.replace("{today}", today).replace("{transcript}", transcript[:8000])

    payload = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "max_tokens": 2000
    }).encode()

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/AlessandroTrimarco/meetingmind"
        }
    )

    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())

    raw = result["choices"][0]["message"]["content"].strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return json.loads(raw)


def transcribe_audio(audio_path: str) -> str:
    try:
        import whisper
        print(f"Transcribing {audio_path}...")
        model = whisper.load_model("base.en")
        return model.transcribe(audio_path)["text"]
    except ImportError:
        raise ImportError("Install whisper: pip install openai-whisper")


class NotionMCPClient:
    def __init__(self, token: str):
        self.token = token

    def _call_mcp(self, tool: str, params: dict) -> dict:
        request = json.dumps({
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": tool, "arguments": params},
            "id": 1
        })
        env = {
            **os.environ,
            "OPENAPI_MCP_HEADERS": json.dumps({
                "Authorization": f"Bearer {self.token}",
                "Notion-Version": "2022-06-28"
            })
        }
        result = subprocess.run(
            ["npx", "-y", "@notionhq/notion-mcp-server"],
            input=request, capture_output=True, text=True, timeout=30, env=env
        )
        if result.returncode != 0:
            raise RuntimeError(f"MCP error: {result.stderr[:500]}")
        return json.loads(result.stdout)

    def create_meeting_page(self, database_id: str, data: dict) -> str:
        today = datetime.now().strftime("%Y-%m-%d")
        properties = {
            "Name": {"title": [{"text": {"content": data["meeting_title"]}}]},
            "Date": {"date": {"start": data.get("date") or today}},
            "Participants": {"multi_select": [
                {"name": p["name"][:100]} for p in data.get("participants", [])[:10]
            ]},
            "Topics": {"multi_select": [
                {"name": t[:100]} for t in data.get("key_topics", [])[:10]
            ]},
            "Sentiment": {"select": {"name": data.get("sentiment", "neutral").capitalize()}},
            "Action Items": {"number": len(data.get("action_items", []))},
            "Decisions": {"number": len(data.get("decisions", []))}
        }
        result = self._call_mcp("API-post-page", {
            "parent": {"database_id": database_id},
            "properties": properties,
            "children": self._build_blocks(data)
        })
        return result.get("result", {}).get("id", "")

    def _build_blocks(self, data: dict) -> list:
        blocks = []
        def h2(text):
            return {"object": "block", "type": "heading_2",
                    "heading_2": {"rich_text": [{"text": {"content": text}}]}}
        def para(text):
            return {"object": "block", "type": "paragraph",
                    "paragraph": {"rich_text": [{"text": {"content": text}}]}}
        def todo(text):
            return {"object": "block", "type": "to_do",
                    "to_do": {"rich_text": [{"text": {"content": text}}], "checked": False}}
        def bullet(text):
            return {"object": "block", "type": "bulleted_list_item",
                    "bulleted_list_item": {"rich_text": [{"text": {"content": text}}]}}

        blocks += [h2("Summary"), para(data.get("summary", ""))]

        if data.get("action_items"):
            blocks.append(h2("Action Items"))
            for item in data["action_items"]:
                tag = {"high": "[HIGH]", "medium": "[MED]", "low": "[LOW]"}.get(
                    item.get("priority", "medium"), "[?]")
                assignee = f" -> {item['assignee']}" if item.get("assignee") else ""
                due = f" (due: {item['due_date']})" if item.get("due_date") else ""
                blocks.append(todo(f"{tag} {item['task']}{assignee}{due}"))

        if data.get("decisions"):
            blocks.append(h2("Decisions"))
            for d in data["decisions"]:
                owner = f" (Owner: {d['owner']})" if d.get("owner") else ""
                blocks.append(bullet(f"{d['decision']}{owner}"))

        if data.get("blockers"):
            blocks.append(h2("Blockers"))
            for b in data["blockers"]:
                blocks.append(bullet(b))

        return blocks[:100]


def main():
    load_env()
    parser = argparse.ArgumentParser(description="MeetingMind -- AI Meeting Intelligence for Notion")
    parser.add_argument("--transcript", help="Path to .txt transcript file")
    parser.add_argument("--audio", help="Path to audio file (requires openai-whisper)")
    parser.add_argument("--text", help="Transcript text inline")
    parser.add_argument("--notion-db", required=True, help="Notion database ID")
    parser.add_argument("--dry-run", action="store_true", help="Extract only, no Notion write")
    args = parser.parse_args()

    if args.audio:
        transcript = transcribe_audio(args.audio)
    elif args.transcript:
        transcript = Path(args.transcript).read_text(encoding="utf-8")
    elif args.text:
        transcript = args.text
    else:
        print("Paste transcript (Ctrl+D when done):")
        transcript = sys.stdin.read()

    print("Extracting meeting intelligence...")
    data = extract_from_transcript(transcript)

    print(f"\nExtracted:")
    print(f"  Title       : {data['meeting_title']}")
    print(f"  Date        : {data.get('date', 'unknown')}")
    print(f"  Participants: {len(data.get('participants', []))}")
    print(f"  Action Items: {len(data.get('action_items', []))}")
    print(f"  Decisions   : {len(data.get('decisions', []))}")
    print(f"  Blockers    : {len(data.get('blockers', []))}")
    print(f"  Sentiment   : {data.get('sentiment', 'unknown')}")

    if args.dry_run:
        print("\n--- Full extraction (dry-run) ---")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    if not os.getenv("NOTION_TOKEN"):
        raise ValueError("Set NOTION_TOKEN in .env")

    print("\nCreating Notion page via MCP...")
    client = NotionMCPClient(os.getenv("NOTION_TOKEN"))
    page_id = client.create_meeting_page(args.notion_db, data)
    clean_id = page_id.replace("-", "") if page_id else ""
    url = f"https://notion.so/{clean_id}" if clean_id else "(no ID returned)"
    print(f"Created: {url}")


if __name__ == "__main__":
    main()
