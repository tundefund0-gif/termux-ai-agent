#!/usr/bin/env python3
"""
Termux AI Agent v3.0 — DeepSeek V4 Flash + wujie272/termux-mcp (80 tools)
══════════════════════════════════════════════════════════════════════════
Real SSE streaming • Reasoning display • Long text generation & input
Futuristic UI • 80 MCP tools • GitHub enabled
══════════════════════════════════════════════════════════════════════════
"""

import json, os, sys, time, subprocess, threading
from pathlib import Path
import requests

# ─── Configuration ───────────────────────────────────────────────────────
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
        except Exception:
            pass
    return cfg

# ─── Futuristic Colors ──────────────────────────────────────────────────
class C:
    reset = "\033[0m"; bold = "\033[1m"; dim = "\033[90m"
    green = "\033[32m"; bgreen = "\033[92m"; yellow = "\033[93m"
    red = "\033[91m"; blue = "\033[94m"; magenta = "\033[95m"
    cyan = "\033[96m"; white = "\033[97m"
    orange = "\033[38;5;214m"; pink = "\033[38;5;213m"
    purple = "\033[38;5;141m"; teal = "\033[38;5;80m"

def color(t, c):
    return f"{c}{t}{C.reset}"

# ─── MCP Client (JSON-RPC 2.0 over stdio) ───────────────────────────────
class MCP:
    def __init__(self):
        self.proc = None
        self._tools = None
        self._lock = threading.Lock()
        self._req_id = 0

    def start(self):
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
            env={**os.environ},
        )
        r = self._send("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "termux-ai-agent", "version": "3.0"},
        })
        if not r or "result" not in r:
            return False
        self._notify("notifications/initialized")
        return True

    def stop(self):
        if self.proc:
            try:
                self.proc.terminate()
            except Exception:
                pass
            self.proc = None

    def _next_id(self):
        self._req_id += 1
        return self._req_id

    def _send(self, method, params=None, id_val=None):
        if not self.proc or not self.proc.stdin:
            return None
        msg = {"jsonrpc": "2.0", "method": method, "id": id_val or self._next_id()}
        if params:
            msg["params"] = params
        with self._lock:
            self.proc.stdin.write(json.dumps(msg) + "\n")
            self.proc.stdin.flush()
            try:
                resp = self.proc.stdout.readline()
            except Exception:
                return None
        try:
            return json.loads(resp.strip())
        except Exception:
            return None

    def _notify(self, method, params=None):
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
            tools_raw = r["result"].get("tools", [])
            openai_tools = []
            for t in tools_raw:
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
        r = self._send("tools/call", {"name": tool_name, "arguments": args})
        if not r:
            return "[MCP Error: No response from server]"
        if "error" in r:
            return f"[MCP Error: {r['error'].get('message', str(r['error']))}]"
        content = r.get("result", {}).get("content", [])
        texts = [c.get("text", "") for c in content if c.get("type") == "text"]
        return "\n".join(texts) if texts else json.dumps(r["result"], indent=2)

# ─── MCP Auto-Installer ─────────────────────────────────────────────────
def install_mcp():
    if os.path.isdir(MCP_DIR):
        return True
    print(f"  {color('⟳', C.yellow)} {color('Installing wujie272/termux-mcp...', C.dim)}")
    try:
        subprocess.run(
            ["git", "clone", "https://github.com/wujie272/termux-mcp.git", MCP_DIR],
            capture_output=True, check=True
        )
    except Exception:
        print(f"  {color('✖', C.red)} Git clone failed. Check internet.", C.red)
        return False
    for pkg_cmd in [
        ["pip3", "install", "mcp", "requests"],
        ["pip3", "install", "mcp", "requests", "--break-system-packages"],
    ]:
        try:
            subprocess.run(pkg_cmd, capture_output=True)
        except Exception:
            pass
    # Enable GitHub tools
    app_py = Path(MCP_DIR) / "termux_mcp" / "app.py"
    if app_py.exists():
        content = app_py.read_text()
        if "# import termux_mcp.tools.github" in content:
            content = content.replace("# import termux_mcp.tools.github", "import termux_mcp.tools.github")
            app_py.write_text(content)
            print(f"  {color('✓', C.green)} GitHub tools enabled", C.dim)
    return True

# ─── LLM Client with SSE Streaming ──────────────────────────────────────
class LLM:
    def __init__(self, config, tools):
        self.config = config
        self.tools = tools
        self.session = requests.Session()

    def _headers(self):
        h = {"Content-Type": "application/json"}
        if self.config.get("api_key"):
            h["Authorization"] = f"Bearer {self.config['api_key']}"
        return h

    def _payload(self, messages, stream=False):
        p = {
            "model": self.config["model"],
            "messages": messages,
            "max_tokens": self.config.get("max_tokens", 65536),
            "temperature": self.config.get("temperature", 0.7),
            "top_p": self.config.get("top_p", 0.95),
            "stream": stream,
        }
        if self.tools:
            p["tools"] = self.tools
            p["tool_choice"] = "auto"
        return p

    def chat(self, messages):
        """Non-streaming call — for tool detection."""
        resp = self.session.post(
            self.config["base_url"] + "/chat/completions",
            headers=self._headers(),
            json=self._payload(messages, stream=False),
            timeout=180,
        )
        resp.raise_for_status()
        return resp.json()

    def chat_stream(self, messages):
        """
        Streaming SSE call — yields (content, reasoning, is_done) tuples.
        Accumulates tool calls silently. At the end yields the full msg dict.
        """
        resp = self.session.post(
            self.config["base_url"] + "/chat/completions",
            headers=self._headers(),
            json=self._payload(messages, stream=True),
            stream=True,
            timeout=180,
        )
        resp.raise_for_status()

        full_content = ""
        full_reasoning = ""
        tool_calls = {}
        in_reasoning = False

        for line in resp.iter_lines():
            if not line:
                continue
            if line.startswith(b"data: "):
                data = line[6:].decode("utf-8").strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices", [])
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                finish = choices[0].get("finish_reason")

                # Reasoning content (DeepSeek shows this before answering)
                rc = delta.get("reasoning_content")
                if rc:
                    full_reasoning += rc
                    if not in_reasoning:
                        in_reasoning = True
                    yield ("reasoning", rc, False)

                # Regular content
                content = delta.get("content")
                if content:
                    full_content += content
                    if in_reasoning:
                        in_reasoning = False
                        yield ("end_reasoning", "", False)
                    yield ("content", content, False)

                # Tool calls
                tc = delta.get("tool_calls")
                if tc:
                    for tcc in tc:
                        idx = tcc.get("index", 0)
                        if idx not in tool_calls:
                            tool_calls[idx] = {
                                "id": tcc.get("id", ""),
                                "type": "function",
                                "function": {"name": "", "arguments": ""}
                            }
                        fn = tcc.get("function", {})
                        if fn.get("name"):
                            tool_calls[idx]["function"]["name"] += fn["name"]
                        if fn.get("arguments"):
                            tool_calls[idx]["function"]["arguments"] += fn["arguments"]
                        if tcc.get("id"):
                            tool_calls[idx]["id"] = tcc["id"]

                if finish == "stop":
                    break

        # Build final message
        msg = {"role": "assistant", "content": full_content}
        if full_reasoning:
            msg["reasoning_content"] = full_reasoning
        if tool_calls:
            sorted_calls = [tool_calls[i] for i in sorted(tool_calls.keys())]
            msg["tool_calls"] = sorted_calls
        yield ("done", msg, True)

# ─── Conversation History Management ────────────────────────────────────
def trim_history(msgs, max_turns=40):
    """Keep conversation manageable while preserving context."""
    if len(msgs) <= max_turns:
        return msgs
    keep = [msgs[0]]  # system prompt
    user_msgs = []
    # Find last 3 user messages
    for i in range(len(msgs) - 1, -1, -1):
        if msgs[i]["role"] == "user":
            user_msgs.insert(0, msgs[i])
            if len(user_msgs) >= 3:
                break
    keep.extend(user_msgs)
    # Add last N-3 messages around those
    cutoff = max(1, len(msgs) - (max_turns - len(keep)))
    for i in range(cutoff, len(msgs)):
        if msgs[i] not in keep:
            keep.append(msgs[i])
    return keep

# ─── User Input (with multiline + file support) ─────────────────────────
def get_user_input():
    raw = input(f"  {color('You', C.blue)} {color('›', C.cyan)} ").strip()
    if not raw:
        return ""

    # Multiline mode: """..."""
    if raw in ('"""', "'''", "%%%"):
        delimiter = raw
        print(f"  {color('(multiline mode — end with ' + delimiter + ')', C.dim)}")
        lines = []
        try:
            while True:
                line = input(f"  {color('...', C.dim)} ")
                if line.strip() == delimiter:
                    break
                lines.append(line)
        except (EOFError, KeyboardInterrupt):
            pass
        return "\n".join(lines)

    # File input: @/path/to/file
    if raw.startswith("@"):
        fpath = os.path.expanduser(raw[1:].strip())
        if os.path.isfile(fpath):
            try:
                content = Path(fpath).read_text()
                print(f"  {color(f'✓ Loaded {len(content)} chars', C.dim)}")
                return content
            except Exception as e:
                print(f"  {color(f'✖ {e}', C.red)}")
        else:
            print(f"  {color('✖ File not found: ' + fpath, C.red)}")
        return ""
    return raw

# ─── Streaming Display ──────────────────────────────────────────────────
def display_streaming_response(mcp, llm, msgs, msg):
    """Display a streaming text response, or process tool calls."""
    if msg.get("tool_calls"):
        msgs.append(msg)
        for tc in msg["tool_calls"]:
            name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"]["arguments"])
            except Exception:
                args = {}
            preview = json.dumps(args)
            if len(preview) > 60:
                preview = preview[:60] + "…"
            print(f"  {color('◆', C.magenta)} {color(name, C.cyan)} {color(preview, C.dim)}", end="", flush=True)
            result = mcp.call(name, args)
            rlen = len(result)
            if rlen < 100:
                col = C.green
                tag = "S"
            elif rlen < 5000:
                col = C.yellow
                tag = "M"
            else:
                col = C.red
                tag = "L"
            print(f" {color(f'[{tag}|{rlen}b]', col)}")
            if rlen > 50000:
                result = result[:50000] + f"\n... [truncated {rlen - 50000} more bytes]"
            msgs.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
        print(f"  {color('·' * 40, C.dim)}")
        return True  # had tool calls, should continue
    else:
        flush_before = ""
        # Stream the response
        print(f"  {color('AI', C.green)} {color('›', C.green)} ", end="", flush=True)
        for evt_type, data, done in llm.chat_stream(msgs):
            if evt_type == "reasoning":
                if not flush_before:
                    print(f"{color('(thinking ', C.dim)}", end="", flush=True)
                    flush_before = "reasoning"
                print(f"{color(data, C.dim)}", end="", flush=True)
            elif evt_type == "end_reasoning":
                print(f"{color(') ', C.dim)}", end="", flush=True)
                flush_before = ""
            elif evt_type == "content":
                print(data, end="", flush=True)
            elif evt_type == "done":
                # data is the msg dict
                msgs.append(data)
        print()
        return False  # no tool calls, conversation turn complete

# ─── System Prompt ──────────────────────────────────────────────────────
SYSTEM_PROMPT = (
    "You are TermuxAI, an AI assistant controlling an Android device via Termux MCP.\n"
    "You have 80 tools: shell commands, file system, UI automation, ADB/Shizuku,\n"
    "app management, communication (SMS/calls/clipboard), device sensors, media,\n"
    "GitHub, and more.\n\n"
    "RULES:\n"
    "- Execute commands immediately when asked — don't just describe\n"
    "- Show clear results after each action\n"
    "- If something fails, try alternatives or explain clearly\n"
    "- Be concise but thorough\n"
    "- You can generate long text, code, and analysis"
)

# ─── Banner ─────────────────────────────────────────────────────────────
BANNER = (
    f"\n"
    f"  {color('╔══════════════════════════════════════════════════╗', C.cyan)}\n"
    f"  {color('║', C.cyan)}  {color('⚡ TERMUX AI AGENT', C.bold)} {color('v3.0', C.dim)}              {color('║', C.cyan)}\n"
    f"  {color('║', C.cyan)}  {color('DeepSeek V4 Flash', C.green)} {color('×', C.dim)} {color('wujie272 MCP', C.magenta)} {color('80 tools', C.dim)} {color('║', C.cyan)}\n"
    f"  {color('║', C.cyan)}  {color('SSE Streaming • Reasoning • Long Text', C.dim)} {color('║', C.cyan)}\n"
    f"  {color('╚══════════════════════════════════════════════════╝', C.cyan)}"
)

# ─── Main Loop ──────────────────────────────────────────────────────────
def main():
    config = load_config()

    os.system("clear")
    print(BANNER)

    if not install_mcp():
        sys.exit(1)

    # Start MCP server
    print(f"  {color('⟳', C.yellow)} {color('Booting MCP server...', C.dim)}", end="", flush=True)
    mcp = MCP()
    if not mcp.start():
        print(f" {color('✖', C.red)}")
        print(f"  {color('Failed to start termux-mcp', C.red)}")
        sys.exit(1)
    print(f" {color('✓', C.green)}")

    tools = mcp.get_tools()
    print(f"  {color('✓', C.green)} {color('MCP', C.cyan)} {color(f'({len(tools)} tools loaded)', C.dim)}")
    print(f"  {color('✓', C.green)} {color('DeepSeek V4 Flash', C.green)} {color('(opencode.ai)', C.dim)}")
    print(f"  {color('✓', C.green)} {color('SSE Streaming', C.pink)} {color('•', C.dim)} {color('Reasoning', C.purple)} {color('•', C.dim)} {color('Long Text', C.yellow)}")
    print(f"  {color('─' * 52, C.dim)}")

    llm = LLM(config, tools)
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}]

    while True:
        try:
            raw = get_user_input()
        except (EOFError, KeyboardInterrupt):
            print(f"\n  {color('Bye! 👋', C.green)}")
            break

        if not raw:
            continue
        if raw.lower() in ("exit", "quit", "q", "/bye"):
            print(f"  {color('Bye! 👋', C.green)}")
            break
        if raw.lower() == "/clear":
            msgs = [msgs[0]]
            os.system("clear")
            print(BANNER)
            print(f"  {color('Conversation cleared', C.dim)}")
            print(f"  {color('─' * 52, C.dim)}")
            continue
        if raw.lower() == "/help":
            print(f"  {color('Commands:', C.dim)}")
            print(f"    {color('/clear', C.yellow)}     — Clear chat history")
            print(f"    {color('/bye', C.yellow)}       — Exit")
            print(f"    {color('\"\"\"...\"\"\"', C.yellow)}  — Multiline input")
            print(f"    {color('@/path/to/file', C.yellow)} — Read from file")
            print(f"  {color('─' * 52, C.dim)}")
            continue

        msgs.append({"role": "user", "content": raw})

        try:
            # First call: detect tool_calls vs text
            data = llm.chat(msgs)
            choice = data["choices"][0]
            msg = choice["message"]

            while True:
                needs_continue = display_streaming_response(mcp, llm, msgs, msg)
                if not needs_continue:
                    break
                # Follow-up after tool calls
                print(f"  {color('AI', C.green)} {color('⟳ follow-up...', C.dim)}", end="\r")
                sys.stdout.flush()
                data = llm.chat(msgs)
                msg = data["choices"][0]["message"]
                print(" " * 50, end="\r")

            msgs = trim_history(msgs)

        except Exception as e:
            print(" " * 50, end="\r")
            print(f"  {color('✖ Error:', C.red)} {color(str(e)[:200], C.red)}")

        print(f"  {color('─' * 52, C.dim)}")

    mcp.stop()
    print(f"  {color('MCP server shut down.', C.dim)}")

if __name__ == "__main__":
    main()
