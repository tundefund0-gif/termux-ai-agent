#!/usr/bin/env python3
"""
Termux AI Agent — DeepSeek V4 Flash (free) + wujie272/termux-mcp (MCP)
Controls Android via proper MCP protocol (JSON-RPC 2.0 over stdio).
"""

import json, os, sys, time, subprocess, socket, threading
from pathlib import Path
import requests

# ─── Config ────────────────────────────────────────────────────────────────
CONFIG_FILE = Path.home() / ".termux-agent.json"
MCP_DIR = os.path.expanduser("~/wujie-mcp-test")

DEFAULT_CONFIG = {
    "api_key": "",
    "base_url": "https://opencode.ai/zen/v1",
    "model": "deepseek-v4-flash-free",
    "max_tokens": 65536,
    "temperature": 0.7,
    "top_p": 0.95,
}

def load_config():
    cfg = DEFAULT_CONFIG.copy()
    if CONFIG_FILE.exists():
        try:
            cfg.update(json.loads(CONFIG_FILE.read_text()))
        except: pass
    return cfg

# ─── Colors ────────────────────────────────────────────────────────────────
class C:
    reset = "\033[0m"; bold = "\033[1m"; dim = "\033[90m"
    green = "\033[32m"; bgreen = "\033[92m"; yellow = "\033[93m"
    red = "\033[91m"; blue = "\033[94m"; magenta = "\033[95m"
    cyan = "\033[96m"; white = "\033[97m"

def color(t, c): return f"{c}{t}{C.reset}"

# ─── MCP Client ────────────────────────────────────────────────────────────
class MCP:
    """Communicates with termux-mcp via MCP stdio protocol (JSON-RPC 2.0)."""
    def __init__(self):
        self.proc = None
        self._tools = None
        self._lock = threading.Lock()
        self._req_id = 0

    def start(self):
        """Spawn the MCP server in stdio mode."""
        if not os.path.isdir(MCP_DIR):
            return False
        self.proc = subprocess.Popen(
            ["python3", "server.py"],
            cwd=MCP_DIR,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        # Initialize handshake
        r = self._send("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "termux-ai-agent", "version": "2.0"},
        })
        if not r or "result" not in r:
            return False
        # Send initialized notification
        self._notify("notifications/initialized")
        return True

    def stop(self):
        if self.proc:
            try: self.proc.terminate()
            except: pass
            self.proc = None

    def _next_id(self):
        self._req_id += 1
        return self._req_id

    def _send(self, method, params=None, id=None):
        """Send a JSON-RPC request and read the response."""
        if not self.proc or not self.proc.stdin:
            return None
        msg = {"jsonrpc": "2.0", "method": method, "id": id or self._next_id()}
        if params:
            msg["params"] = params
        with self._lock:
            self.proc.stdin.write(json.dumps(msg) + "\n")
            self.proc.stdin.flush()
            resp = self.proc.stdout.readline()
        try:
            return json.loads(resp.strip())
        except:
            return None

    def _notify(self, method, params=None):
        """Send a JSON-RPC notification (no response expected)."""
        if not self.proc or not self.proc.stdin:
            return
        msg = {"jsonrpc": "2.0", "method": method}
        if params:
            msg["params"] = params
        with self._lock:
            self.proc.stdin.write(json.dumps(msg) + "\n")
            self.proc.stdin.flush()

    def get_tools(self):
        if self._tools:
            return self._tools
        r = self._send("tools/list")
        if r and "result" in r:
            tools = r["result"].get("tools", [])
            # Convert MCP schemas to OpenAI-compatible format
            openai_tools = []
            for t in tools:
                ot = {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t.get("description", ""),
                        "parameters": t.get("inputSchema", {"type": "object", "properties": {}}),
                    }
                }
                openai_tools.append(ot)
            self._tools = openai_tools
            return self._tools
        return []

    def call(self, tool_name, args):
        """Call a tool via MCP tools/call and return the text result."""
        r = self._send("tools/call", {"name": tool_name, "arguments": args})
        if not r:
            return "[MCP Error: No response]"
        if "error" in r:
            return f"[MCP Error: {r['error'].get('message', 'unknown')}]"
        result = r.get("result", {})
        content = result.get("content", [])
        parts = []
        is_error = result.get("isError", False)
        for c in content:
            if c.get("type") == "text":
                parts.append(c["text"])
            elif c.get("type") == "resource":
                parts.append(str(c.get("resource", {})))
        output = "\n".join(parts)
        if is_error:
            output = f"[Error] {output}"
        return output

# ─── LLM Client ────────────────────────────────────────────────────────────
class LLM:
    def __init__(self, config, tools):
        self.key = config.get("api_key", "")
        self.base = config["base_url"].rstrip("/")
        self.model = config["model"]
        self.max_tokens = config.get("max_tokens", 65536)
        self.temp = config.get("temperature", 0.7)
        self.top_p = config.get("top_p", 0.95)
        self.tools = tools

    def chat(self, messages):
        body = {
            "model": self.model, "messages": messages,
            "max_tokens": self.max_tokens, "temperature": self.temp, "top_p": self.top_p,
        }
        if self.tools:
            body["tools"] = self.tools
            body["tool_choice"] = "auto"

        headers = {"Content-Type": "application/json"}
        if self.key:
            headers["Authorization"] = f"Bearer {self.key}"

        r = requests.post(f"{self.base}/chat/completions", headers=headers, json=body, timeout=120)
        if r.status_code != 200:
            raise RuntimeError(f"API {r.status_code}: {r.text[:200]}")
        return r.json()

# ─── Install MCP Server ────────────────────────────────────────────────────
def install_mcp():
    """Clone wujie272/termux-mcp if not present."""
    if os.path.isdir(MCP_DIR):
        return True
    print(f"  {color('⟳', C.yellow)} {color('Installing wujie272/termux-mcp...', C.dim)}", end="", flush=True)
    try:
        r = subprocess.run(
            ["git", "clone", "--depth", "1",
             "https://github.com/wujie272/termux-mcp.git", MCP_DIR],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            print(f" {color('✖', C.red)}")
            print(f"  {r.stderr[:200]}")
            return False
        print(f" {color('✓', C.green)}")
        # Install deps
        print(f"  {color('⟳', C.yellow)} {color('Installing Python deps...', C.dim)}", end="", flush=True)
        r2 = subprocess.run(
            ["pip3", "install", "mcp"],
            capture_output=True, text=True, timeout=120,
        )
        if r2.returncode == 0 or "already satisfied" in r2.stdout:
            print(f" {color('✓', C.green)}")
        else:
            print(f" {color('?', C.yellow)} {r2.stdout[-100:]}")
        return True
    except subprocess.TimeoutExpired:
        print(f" {color('✖', C.red)}")
        print(f"  {color('Timed out cloning repo', C.red)}")
        return False
    except Exception as e:
        print(f" {color('✖', C.red)}")
        print(f"  {color(str(e), C.red)}")
        return False

# ─── Agent ─────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are TermuxAI, an AI assistant controlling an Android phone via Termux.
You have 70+ MCP tools: shell commands, file system, device sensors, ADB/Shizuku,
UI automation, app management, communication, media, GitHub, and more.

RULES:
- Use tools to DO things the user asks — don't just describe
- Show results clearly after running commands
- If something fails, try alternatives
- Be concise and helpful"""

BANNER = f"""  {color('┌─────────────────────────────────────────────┐', C.cyan)}
  {color('│', C.cyan)}  {color('⚡ TERMUX AI AGENT', C.bold)} {color('— DeepSeek V4 Flash', C.white)}  {color('│', C.cyan)}
  {color('│', C.cyan)}  {color('× wujie272 MCP    72 tools', C.magenta)}     {color('│', C.cyan)}
  {color('└─────────────────────────────────────────────┘', C.cyan)}"""

def main():
    config = load_config()
    print(BANNER)

    # Install MCP server if needed
    if not install_mcp():
        sys.exit(1)

    # Start MCP server
    print(f"  {color('⟳', C.yellow)} {color('Starting MCP server...', C.dim)}", end="", flush=True)
    mcp = MCP()
    if not mcp.start():
        print(f" {color('✖', C.red)}")
        print(f"  {color('Failed to start termux-mcp', C.red)}")
        sys.exit(1)
    print(f" {color('✓', C.green)}")

    tools = mcp.get_tools()
    print(f"  {color('✓', C.green)} {color('wujie272/termux-mcp', C.cyan)} {color(f'({len(tools)} tools)', C.dim)}")
    print(f"  {color('✓', C.green)} {color('DeepSeek V4 Flash', C.green)} {color('(free)', C.dim)}")
    print(f"  {color('─', C.dim) * 47}\n")

    llm = LLM(config, tools)
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}]

    try:
        while True:
            try:
                raw = input(f"  {color('You', C.blue)} {color('›', C.cyan)} ").strip()
            except (EOFError, KeyboardInterrupt):
                print(f"\n  {color('Bye!', C.dim)}")
                break

            if not raw: continue
            if raw.lower() in ("exit", "quit", "q"):
                print(f"  {color('Bye!', C.dim)}")
                break

            msgs.append({"role": "user", "content": raw})

            for _ in range(20):
                print(f"  {color('AI', C.green)} {color('● thinking...', C.dim)}", end="\r")
                sys.stdout.flush()

                try:
                    data = llm.chat(msgs)
                except Exception as e:
                    print(" " * 50, end="\r")
                    print(f"  {color('✖', C.red)} {color(str(e)[:120], C.red)}")
                    break

                choice = data["choices"][0]
                msg = choice["message"]
                finish = choice.get("finish_reason", "")
                msgs.append(msg)
                print(" " * 50, end="\r")

                if finish == "stop" or not msg.get("tool_calls"):
                    content = msg.get("content", "") or ""
                    print(f"  {color('AI', C.green)} {color('›', C.green)} ", end="", flush=True)
                    for ch in content:
                        print(ch, end="", flush=True)
                        time.sleep(0.01)
                    print()
                    break

                for tc in msg["tool_calls"]:
                    name = tc["function"]["name"]
                    try:
                        args = json.loads(tc["function"]["arguments"])
                    except:
                        args = {}
                    preview = json.dumps(args)
                    if len(preview) > 60:
                        preview = preview[:60] + "…"
                    print(f"  {color('◆', C.magenta)} {color(name, C.magenta)} {color(preview, C.dim)}", end="", flush=True)
                    result = mcp.call(name, args)
                    rlen = len(result)
                    col = C.green if rlen < 100 else C.yellow if rlen < 5000 else C.red
                    print(f" {color(f'[{rlen}b]', col)}")
                    msgs.append({"role": "tool", "tool_call_id": tc["id"], "content": result})

            if len(msgs) > 50:
                keep = [msgs[0]]
                for i in range(len(msgs)-1, -1, -1):
                    if msgs[i]["role"] == "user":
                        keep.append(msgs[i])
                        break
                keep.extend(msgs[-20:])
                msgs = keep

            print(f"  {color('·' * 40, C.dim)}\n")
    finally:
        mcp.stop()

if __name__ == "__main__":
    main()
