"""
tools/claude_code.py — Claude-powered code generation tool for Briven.

Uses the Anthropic API (claude-sonnet-4-6 by default) to generate, review,
or explain code. Results are returned as text or written to a file.

Requires: ANTHROPIC_API_KEY in .env

Usage:
    python tools/claude_code.py --prompt "Write a Python function to parse ISO dates"
    python tools/claude_code.py --prompt "Review this code" --file mycode.py
    python tools/claude_code.py --prompt "Add type hints" --file mycode.py --output fixed.py
"""

import argparse
import os
import sys
from pathlib import Path


def generate_code(
    prompt: str,
    context_code: str | None = None,
    model: str = "claude-sonnet-4-6",
    api_key: str | None = None,
    max_tokens: int = 4096,
) -> str:
    """Call the Anthropic API and return the generated code/text."""
    try:
        import anthropic
    except ImportError:
        raise ImportError(
            "anthropic package not installed. Run: pip install anthropic"
        )

    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError("ANTHROPIC_API_KEY not set in environment or .env")

    client = anthropic.Anthropic(api_key=key)

    system = (
        "You are an expert Python developer embedded in the Briven framework. "
        "Generate clean, correct, well-documented code. "
        "Return only the code (with brief inline comments where helpful), "
        "no markdown fences unless the user asks for them."
    )

    user_content = prompt
    if context_code:
        user_content = f"Here is the existing code:\n\n```python\n{context_code}\n```\n\n{prompt}"

    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_content}],
    )
    return message.content[0].text


def main() -> None:
    parser = argparse.ArgumentParser(description="Claude code generation for Briven")
    parser.add_argument("--prompt", "-p", required=True, help="What to generate or do")
    parser.add_argument("--file", "-f", help="Input code file to use as context")
    parser.add_argument("--output", "-o", help="Write output to this file (default: stdout)")
    parser.add_argument("--model", default="claude-sonnet-4-6", help="Anthropic model to use")
    parser.add_argument("--max-tokens", type=int, default=4096, help="Max tokens in response")
    args = parser.parse_args()

    context = None
    if args.file:
        context = Path(args.file).read_text(encoding="utf-8")

    try:
        result = generate_code(
            prompt=args.prompt,
            context_code=context,
            model=args.model,
            max_tokens=args.max_tokens,
        )
    except Exception as e:
        print(f"[claude_code] Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        Path(args.output).write_text(result, encoding="utf-8")
        print(f"[claude_code] Output written to {args.output}")
    else:
        print(result)


if __name__ == "__main__":
    main()
