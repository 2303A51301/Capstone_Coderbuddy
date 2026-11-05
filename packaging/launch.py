"""Entry point for the Windows bundle; credentials and data stay outside the install."""

from __future__ import annotations

import getpass
import os
from pathlib import Path
import socket
import threading
import time
import urllib.request
import webbrowser

from dotenv import dotenv_values, load_dotenv, set_key
import uvicorn


def main() -> None:
    root = Path(__file__).resolve().parent
    home = Path(os.environ["LOCALAPPDATA"]) / "CoderBuddy-CaPStone"
    home.mkdir(parents=True, exist_ok=True)
    config = home / ".env"
    if not config.exists():
        config.write_text(
            "AI_PROVIDER=azure-foundry\n"
            "AZURE_OPENAI_RESPONSES_ENDPOINT=\n"
            "AZURE_OPENAI_DEPLOYMENT=gpt-4.1-mini\n"
            "AZURE_OPENAI_API_KEY=\n",
            encoding="utf-8",
        )
    saved = dotenv_values(config)
    if saved.get("AI_PROVIDER") == "azure-foundry" and not all(
        saved.get(key) for key in (
            "AZURE_OPENAI_RESPONSES_ENDPOINT",
            "AZURE_OPENAI_DEPLOYMENT",
            "AZURE_OPENAI_API_KEY",
        )
    ):
        print("First-time Azure setup. Settings are saved only in your Windows profile.")
        print("Close this window to cancel. Never share the saved .env file.")
        endpoint = input("Azure Responses endpoint URL: ").strip()
        from urllib.parse import urlparse
        parsed = urlparse(endpoint)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("An HTTPS endpoint without embedded credentials is required.")
        deployment = input("Azure deployment name [gpt-4.1-mini]: ").strip() or "gpt-4.1-mini"
        key = getpass.getpass("Azure API key (hidden while typing): ").strip()
        if not key:
            raise ValueError("An API key is required.")
        for name, value in {
            "AZURE_OPENAI_RESPONSES_ENDPOINT": endpoint,
            "AZURE_OPENAI_DEPLOYMENT": deployment,
            "AZURE_OPENAI_API_KEY": key,
        }.items():
            set_key(config, name, value)
    load_dotenv(config, override=True)
    os.environ["WORKSPACE_ROOT"] = str(home / "workspace")
    os.environ["RUN_DATABASE"] = str(home / "data" / "coderbuddy.sqlite3")
    os.environ["PATH"] = str(root / "runtime") + os.pathsep + os.environ.get("PATH", "")
    os.chdir(root)
    port = None
    for candidate in range(8010, 8031):
        try:
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", candidate))
        except OSError:
            continue
        port = candidate
        break
    if port is None:
        raise RuntimeError("No free local port in 8010-8030. Close an earlier instance.")
    url = f"http://127.0.0.1:{port}"

    def open_when_ready() -> None:
        for _ in range(60):
            try:
                with urllib.request.urlopen(url, timeout=1) as response:
                    if response.status == 200:
                        webbrowser.open(url)
                        return
            except OSError:
                time.sleep(1)
        print(f"Browser did not open automatically. Check server errors, then open {url}.")

    threading.Thread(target=open_when_ready, daemon=True).start()
    print(f"CoderBuddy: {url}\nKeep this window open. Press Ctrl+C to stop.")
    uvicorn.run("app.main:app", host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
