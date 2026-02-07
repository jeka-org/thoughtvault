#!/usr/bin/env python3
"""
Auto-capture important information from conversations.

Uses local LLM (Ollama) to extract:
- Decisions made
- Projects mentioned
- Lessons learned
- Todos/action items

Usage:
    ./capture.py "conversation text"
    ./capture.py --file transcript.txt
    ./capture.py --stdin
"""
import sys
import argparse
import json
import requests
from datetime import datetime
from pathlib import Path

OLLAMA_URL = "http://localhost:11434"
MODEL = "llama3.2:3b"

EXTRACTION_PROMPT = """Analyze this conversation and extract important information.

Return a JSON object with these fields:
- decisions: list of decisions made (empty if none)
- projects: list of project names mentioned (empty if none)
- lessons: list of lessons learned or insights (empty if none)
- todos: list of action items or todos (empty if none)
- summary: one sentence summary of what happened

Only include items that are clearly present. Don't invent or assume.
Return ONLY valid JSON, no other text.

Conversation:
---
{text}
---

JSON:"""

def extract_from_conversation(text: str) -> dict:
    """Use local LLM to extract structured info from conversation."""
    prompt = EXTRACTION_PROMPT.format(text=text[:4000])  # Limit input size
    
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "format": "json"
            },
            timeout=60
        )
        response.raise_for_status()
        
        result = response.json()
        raw_output = result.get("response", "{}")
        
        # Parse JSON from output
        try:
            return json.loads(raw_output)
        except json.JSONDecodeError:
            # Try to find JSON in output
            import re
            match = re.search(r'\{[^{}]*\}', raw_output, re.DOTALL)
            if match:
                return json.loads(match.group())
            return {"error": "Could not parse output", "raw": raw_output}
    
    except Exception as e:
        return {"error": str(e)}

def append_to_memory(extracted: dict, memory_dir: Path):
    """Append extracted info to memory files."""
    today = datetime.now().strftime("%Y-%m-%d")
    memory_file = memory_dir / f"{today}.md"
    
    lines = []
    
    if extracted.get("summary"):
        lines.append(f"\n### Auto-captured ({datetime.now().strftime('%H:%M')})")
        lines.append(f"**Summary:** {extracted['summary']}\n")
    
    if extracted.get("decisions"):
        lines.append("**Decisions:**")
        for d in extracted["decisions"]:
            lines.append(f"- {d}")
        lines.append("")
    
    if extracted.get("projects"):
        lines.append("**Projects mentioned:**")
        for p in extracted["projects"]:
            lines.append(f"- {p}")
        lines.append("")
    
    if extracted.get("lessons"):
        lines.append("**Lessons:**")
        for l in extracted["lessons"]:
            lines.append(f"- {l}")
        lines.append("")
    
    if extracted.get("todos"):
        lines.append("**Todos:**")
        for t in extracted["todos"]:
            lines.append(f"- [ ] {t}")
        lines.append("")
    
    if lines:
        with open(memory_file, "a") as f:
            f.write("\n".join(lines))
        print(f"✓ Appended to {memory_file}")
    else:
        print("Nothing significant to capture")

def main():
    parser = argparse.ArgumentParser(description="Auto-capture from conversations")
    parser.add_argument("text", nargs="?", type=str, help="Conversation text")
    parser.add_argument("--file", type=Path, help="Read from file")
    parser.add_argument("--stdin", action="store_true", help="Read from stdin")
    parser.add_argument("--memory-dir", type=Path, 
                        default=Path.home() / ".openclaw/workspace/memory",
                        help="Memory directory to append to")
    parser.add_argument("--dry-run", action="store_true", 
                        help="Don't write to files, just print extraction")
    
    args = parser.parse_args()
    
    # Get input text
    if args.stdin:
        text = sys.stdin.read()
    elif args.file:
        text = args.file.read_text()
    elif args.text:
        text = args.text
    else:
        print("Error: Provide text, --file, or --stdin")
        sys.exit(1)
    
    print("Extracting information...")
    extracted = extract_from_conversation(text)
    
    if "error" in extracted:
        print(f"Error: {extracted['error']}")
        sys.exit(1)
    
    print(json.dumps(extracted, indent=2))
    
    if not args.dry_run:
        append_to_memory(extracted, args.memory_dir)

if __name__ == "__main__":
    main()
