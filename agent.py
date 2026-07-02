#!/usr/bin/env python3
"""
Termux AI Agent v4.0 — DeepSeek V4 Flash + termuxgpt/termux-mcp (REST API)
══════════════════════════════════════════════════════════════════════════
SSE streaming • Reasoning display • 103 tools • Smart loop detection
══════════════════════════════════════════════════════════════════════════
"""

import json, os, sys, time, subprocess, threading, signal
from pathlib import Path
from http.client import HTTPConnection
import requests

# ─── Config ───────────────────────────────────────────────────────────────
CONFIG_FILE = Path.home() / ".termux-agent.json"
MCP_DIR = os.path.expanduser("~/termux-mcp")
MCP_PORT = 8080
MCP_URL = f"http://127.0.0.1:{MCP_PORT}"

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

# ─── Colors ───────────────────────────────────────────────────────────────
class C:
    reset = "\033[0m"; bold = "\033[1m"; dim = "\033[90m"
    green = "\033[32m"; bgreen = "\033[92m"; yellow = "\033[93m"
    red = "\033[91m"; blue = "\033[94m"; magenta = "\033[95m"
    cyan = "\033[96m"; white = "\033[97m"
    orange = "\033[38;5;214m"; pink = "\033[38;5;213m"
    purple = "\033[38;5;141m"; teal = "\033[38;5;80m"

def color(t, c):
    return f"{c}{t}{C.reset}"

# ─── MCP Client (REST API) ────────────────────────────────────────────────
class MCP:
    """Communicates with termuxgpt/termux-mcp via REST API on port 8080."""

    # Map tool names to API endpoints
    ENDPOINTS = {
        "run": "/run", "ls": "/ls", "read": "/read", "write": "/write",
        "mkdir": "/mkdir", "delete": "/delete", "search": "/search",
        "screenshot": "/screenshot", "camera_photo": "/camera-photo",
        "camera_info": "/camera-info", "clipboard_get": "/clipboard-get",
        "clipboard_set": "/clipboard-set", "notify": "/notify",
        "notify_remove": "/notify-remove", "share": "/share",
        "open_url": "/open-url", "download": "/download",
        "battery": "/battery", "wifi_info": "/wifi-info",
        "wifi_scan": "/wifi-scan", "location": "/location",
        "contacts": "/contacts", "sms_send": "/sms-send",
        "sms_inbox": "/sms-inbox", "list_apps": "/list-apps",
        "vibrate": "/vibrate", "tts_speak": "/tts-speak",
        "torch": "/torch", "volume": "/volume", "brightness": "/brightness",
        "toast": "/toast", "dialog": "/dialog", "system_info": "/system-info",
        "health": "/health", "process_list": "/process-list",
        "process_kill": "/process-kill", "speedtest": "/speedtest",
        "public_ip": "/public-ip", "weather": "/weather",
        "translate": "/translate", "scan_barcode": "/scan-barcode",
        "qrcode": "/qrcode", "text_extract": "/text-extract",
        "image_process": "/image-process", "video_process": "/video-process",
        "screen_record": "/screen-record", "microphone_record": "/microphone-record",
        "speech_to_text": "/speech-to-text", "media_player": "/media-player",
        "wallpaper": "/wallpaper", "call": "/call",
        "fingerprint": "/fingerprint", "sensor": "/sensor",
        "telephony_cellinfo": "/telephony-cellinfo",
        "telephony_deviceinfo": "/telephony-deviceinfo",
        "infrared": "/infrared", "backup": "/backup", "restore": "/restore",
        "migrate": "/migrate", "diff": "/diff", "patch": "/patch",
        "git_op": "/git-op", "git_pr": "/git-pr", "git_smart": "/git-smart",
        "web_server": "/web-server", "db_query": "/db-query",
        "db_design": "/db-design", "cron_add": "/cron-add",
        "cron_list": "/cron-list", "cron_remove": "/cron-remove",
        "diagnose": "/diagnose", "explain": "/explain",
        "error_explain": "/error-explain", "script_gen": "/script-gen",
        "review": "/review", "log_analyze": "/log-analyze",
        "deps_tree": "/deps-tree", "storage_audit": "/storage-audit",
        "config_fix": "/config-fix", "permission_fix": "/permission-fix",
        "smart_install": "/smart-install", "pkg_smart": "/pkg-smart",
        "dev_env": "/dev-env", "optimize": "/optimize",
        "profile": "/profile", "tutorial": "/tutorial",
        "ssh_wizard": "/ssh-wizard", "service_guard": "/service-guard",
        "history_insight": "/history-insight", "quick_cmd": "/quick-cmd",
        "port_manage": "/port-manage", "recipe_list": "/recipe-list",
        "recipe_run": "/recipe-run", "recipe_save": "/recipe-save",
        "history": "/history", "history_clear": "/history-clear",
        "history_save": "/history-save", "context": "/context",
        "context_save": "/context-save", "cloud_sync": "/cloud-sync",
        "cancel": "/cancel", "storage_get": "/storage-get",
    }

    def __init__(self):
        self.proc = None
        self._tools = None

    def _kill_port(self, port):
        """Kill any process listening on the given port."""
        # Method 1: try fuser
        try:
            subprocess.run(["fuser", "-k", f"{port}/tcp"],
                         capture_output=True, timeout=3)
            return
        except Exception:
            pass
        # Method 2: try reading /proc/net/tcp
        try:
            with open("/proc/net/tcp") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) < 10:
                        continue
                    local = parts[1]  # local_address in hex
                    if ":" in local:
                        hex_port = local.split(":")[1]
                        if int(hex_port, 16) == port:
                            pid_hex = parts[9]
                            pid = int(pid_hex, 16)
                            if pid > 0:
                                try:
                                    os.kill(pid, 9)
                                except Exception:
                                    pass
        except Exception:
            pass
        # Method 3: try ss
        try:
            result = subprocess.run(
                ["ss", "-tlnp"],
                capture_output=True, text=True, timeout=3
            )
            for line in result.stdout.split("\n"):
                if f":{port} " in line and "pid=" in line:
                    pid_str = line.split("pid=")[1].split(",")[0]
                    try:
                        os.kill(int(pid_str), 9)
                    except Exception:
                        pass
        except Exception:
            pass

    def start(self):
        """Start the termuxgpt MCP server in background."""
        if not os.path.isdir(MCP_DIR):
            return False

        # First, kill anything on our port
        try:
            subprocess.run(["fuser", "-k", f"{MCP_PORT}/tcp"],
                         capture_output=True, timeout=3)
            time.sleep(1)
        except Exception:
            pass
        # Also kill leftover MCP processes
        try:
            subprocess.run(["pkill", "-f", "termux_mcp"],
                         capture_output=True, timeout=3)
            time.sleep(0.5)
        except Exception:
            pass

        # Check if already running (after cleanup)
        for _ in range(3):
            try:
                conn = HTTPConnection("127.0.0.1", MCP_PORT, timeout=2)
                conn.request("GET", "/ping")
                resp = conn.getresponse()
                body = resp.read()
                if resp.status == 200:
                    return True  # Already running
            except Exception:
                break

        # Start fresh
        self.proc = subprocess.Popen(
            ["python3", "-m", "termux_mcp"],
            cwd=MCP_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={**os.environ},
        )

        # Wait for server to start (with retries)
        for attempt in range(30):
            time.sleep(0.5)
            try:
                conn = HTTPConnection("127.0.0.1", MCP_PORT, timeout=2)
                conn.request("GET", "/ping")
                resp = conn.getresponse()
                body = resp.read().decode()
                if resp.status == 200 and '"status": "ok"' in body:
                    return True
            except Exception:
                if attempt == 15:
                    # Try again if it might be a port conflict
                    try:
                        subprocess.run(["fuser", "-k", f"{MCP_PORT}/tcp"],
                                     capture_output=True, timeout=3)
                    except Exception:
                        pass
                continue
        return False

    def stop(self):
        if self.proc:
            try:
                self.proc.terminate()
                self.proc.wait(3)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
            self.proc = None
        # Also try to kill any running server and free port
        subprocess.run(["pkill", "-f", "python3.*termux_mcp"], capture_output=True)
        try:
            self._kill_port(MCP_PORT)
        except Exception:
            pass

    def get_tools(self):
        if self._tools:
            return self._tools
        try:
            resp = requests.get(f"{MCP_URL}/tools", timeout=5)
            if resp.status_code == 200:
                self._tools = resp.json().get("tools", [])
                return self._tools
        except Exception:
            pass
        return []

    def call(self, tool_name, args):
        """Call a tool via REST API. Returns text result."""
        endpoint = self.ENDPOINTS.get(tool_name)
        if not endpoint:
            return f"[Error: No endpoint for tool '{tool_name}']"
        try:
            resp = requests.post(
                f"{MCP_URL}{endpoint}",
                json=args or {},
                timeout=(30 if tool_name == "run" else 120),
            )
            if resp.status_code == 200:
                return resp.text
            else:
                try:
                    err = resp.json()
                    return f"[Error: {err.get('error', resp.text[:200])}]"
                except Exception:
                    return f"[Error: HTTP {resp.status_code}]"
        except requests.exceptions.Timeout:
            import sys; sys.stderr.write(f"[MCP Timeout] {tool_name} timed out\n"); sys.stderr.flush()
            return "[Error: Command timed out (120s)]"
        except requests.exceptions.ConnectionError:
            return "[Error: MCP server not reachable]"
        except Exception as e:
            return f"[Error: {str(e)[:120]}]"

# ─── MCP Auto-Installer ────────────────────────────────────────────────
def install_mcp():
    if os.path.isdir(MCP_DIR) and os.path.exists(os.path.join(MCP_DIR, "termux_mcp", "server.py")):
        return True
    print(f"  {color('⟳', C.yellow)} {color('Installing termuxgpt/termux-mcp...', C.dim)}")
    try:
        subprocess.run(
            ["git", "clone", "https://github.com/termuxgpt/termux-mcp.git", MCP_DIR],
            capture_output=True, check=True
        )
    except Exception:
        print(f"  {color('✖', C.red)} Git clone failed.", C.red)
        return False
    for cmd in [
        ["pip3", "install", "requests"],
        ["pip3", "install", "requests", "--break-system-packages"],
    ]:
        try:
            subprocess.run(cmd, capture_output=True)
        except Exception:
            pass
    print(f"  {color('✓', C.green)} termuxgpt/termux-mcp installed", C.dim)
    return True

# ─── Termux:API Probe ───────────────────────────────────────────────────
def probe_failing_tools(mcp):
    """Test which tools fail due to missing Termux:API. Returns warning string or empty."""
    failing = []
    # Keywords that indicate a tool is unavailable
    fail_keywords = ["failed", "not found", "command not found", "error:", "missing",
                     "permission denied", "not installed", "no such file", "unable"]
    for tool_name in ["tts_speak", "battery", "location", "camera_photo"]:
        args = {} if tool_name != "tts_speak" else {"text": "test"}
        result = mcp.call(tool_name, args)
        rl = result.lower()
        if len(result) < 50 or any(kw in rl for kw in fail_keywords):
            failing.append(tool_name)

    if failing:
        return (
            "IMPORTANT: These MCP tools are UNAVAILABLE (Termux:API not installed):\n"
            + ", ".join(failing) + ".\n"
            "They will FAIL if called. DO NOT call them.\n"
            "Alternatives: use 'run' with shell commands instead."
        )
    return ""

# ─── LLM Client ───────────────────────────────────────────────────────────
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

    def _payload(self, messages, stream=False, force_text=False):
        p = {
            "model": self.config["model"],
            "messages": messages,
            "max_tokens": self.config.get("max_tokens", 65536),
            "temperature": self.config.get("temperature", 0.7),
            "top_p": self.config.get("top_p", 0.95),
            "stream": stream,
        }
        if self.tools and not force_text:
            p["tools"] = self.tools
            p["tool_choice"] = "auto"
        return p

    def chat(self, messages, force_text=False):
        resp = self.session.post(
            self.config["base_url"] + "/chat/completions",
            headers=self._headers(),
            json=self._payload(messages, stream=False, force_text=force_text),
            timeout=180,
        )
        resp.raise_for_status()
        return resp.json()

    def chat_stream(self, messages):
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

                rc = delta.get("reasoning_content")
                if rc:
                    full_reasoning += rc
                    if not in_reasoning:
                        in_reasoning = True
                    yield ("reasoning", rc, False)

                content = delta.get("content")
                if content:
                    full_content += content
                    if in_reasoning:
                        in_reasoning = False
                        yield ("end_reasoning", "", False)
                    yield ("content", content, False)

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

        msg = {"role": "assistant", "content": full_content}
        if full_reasoning:
            msg["reasoning_content"] = full_reasoning
        if tool_calls:
            sorted_calls = [tool_calls[i] for i in sorted(tool_calls.keys())]
            msg["tool_calls"] = sorted_calls
        yield ("done", msg, True)

# ─── History Management ───────────────────────────────────────────────────
def trim_history(msgs, max_turns=40):
    if len(msgs) <= max_turns:
        return msgs
    keep = [msgs[0]]
    user_msgs = []
    for i in range(len(msgs) - 1, -1, -1):
        if msgs[i]["role"] == "user":
            user_msgs.insert(0, msgs[i])
            if len(user_msgs) >= 3:
                break
    keep.extend(user_msgs)
    cutoff = max(1, len(msgs) - (max_turns - len(keep)))
    for i in range(cutoff, len(msgs)):
        if msgs[i] not in keep:
            keep.append(msgs[i])
    return keep

# ─── User Input ───────────────────────────────────────────────────────────
def get_user_input():
    raw = input(f"  {color('You', C.blue)} {color('›', C.cyan)} ").strip()
    if not raw:
        return ""
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

# ─── Display & Tool Processing ────────────────────────────────────────────
def process_tool_calls(mcp, msgs, msg):
    """Execute tool calls from the model. Returns True if tools were called."""
    if not msg.get("tool_calls"):
        return False
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
    return True

def stream_response(llm, msgs):
    """Stream the model's text response."""
    print(f"  {color('AI', C.green)} {color('›', C.green)} ", end="", flush=True)
    has_reasoning = False
    for evt_type, data, done in llm.chat_stream(msgs):
        if evt_type == "reasoning":
            if not has_reasoning:
                print(f"{color('(thinking ', C.dim)}", end="", flush=True)
                has_reasoning = True
            print(f"{color(data, C.dim)}", end="", flush=True)
        elif evt_type == "end_reasoning":
            print(f"{color(') ', C.dim)}", end="", flush=True)
            has_reasoning = False
        elif evt_type == "content":
            print(data, end="", flush=True)
        elif evt_type == "done":
            msgs.append(data)
    print()

# ─── System Prompt ────────────────────────────────────────────────────────
SYSTEM_PROMPT = (
    "You are TermuxAI, an AI assistant controlling an Android device via Termux MCP.\n"
    "You have 103 tools: shell commands, file system, UI, sensors, apps,\n"
    "media, network, GitHub, and more.\n\n"
    "RULES:\n"
    "- Execute commands immediately when asked\n"
    "- Show clear results after each action\n"
    "- If something fails, try one alternative, then tell the user\n"
    "- To CREATE files use the 'write' tool with content and file_path\n"
    "- NEVER use cat > heredoc syntax\n"
    "- When creating Python scripts, NEVER use input() or interactive code.\n"
    "  Scripts must run non-interactively (hardcoded values, CLI args, or demo mode).\n"
    "  Interactive scripts will HANG the MCP server and get Killed by the system.\n"
    "- When running scripts, use 'echo <input> | python3 script.py' if input is needed\n"
    "- Be concise but thorough. Generate long code/text when asked."
)

# ─── Banner ───────────────────────────────────────────────────────────────
BANNER = (
    f"\n"
    f"  {color('╔══════════════════════════════════════════════════╗', C.cyan)}\n"
    f"  {color('║', C.cyan)}  {color('⚡ TERMUX AI AGENT', C.bold)} {color('v4.0', C.dim)}              {color('║', C.cyan)}\n"
    f"  {color('║', C.cyan)}  {color('DeepSeek V4 Flash', C.green)} {color('×', C.dim)} {color('termuxgpt MCP', C.magenta)} {color('103 tools', C.dim)} {color('║', C.cyan)}\n"
    f"  {color('║', C.cyan)}  {color('SSE • Reasoning • REST API', C.dim)}         {color('║', C.cyan)}\n"
    f"  {color('╚══════════════════════════════════════════════════╝', C.cyan)}"
)

# ─── Main ─────────────────────────────────────────────────────────────────
def main():
    config = load_config()
    os.system("clear")
    print(BANNER)

    if not install_mcp():
        sys.exit(1)

    # Start MCP server
    print(f"  {color('⟳', C.yellow)} {color('Starting termuxgpt MCP server...', C.dim)}", end="", flush=True)
    mcp = MCP()
    if not mcp.start():
        print(f" {color('✖', C.red)}")
        print(f"  {color('Failed to start MCP server on port 8080', C.red)}")
        sys.exit(1)
    print(f" {color('✓', C.green)}")

    # Get tools
    tools = mcp.get_tools()
    print(f"  {color('✓', C.green)} {color('MCP', C.cyan)} {color(f'({len(tools)} tools loaded)', C.dim)}")

    # Probe for failing tools
    print(f"  {color('⟳', C.yellow)} {color('Testing tool availability...', C.dim)}", end="", flush=True)
    tool_warning = probe_failing_tools(mcp)
    if tool_warning:
        print(f" {color('⚠', C.yellow)}")
        print(f"  {color('⚠', C.yellow)} {color('Some tools unavailable (TTS, battery, etc.)', C.dim)}")
    else:
        print(f" {color('✓', C.green)}")

    print(f"  {color('✓', C.green)} {color('DeepSeek V4 Flash', C.green)} {color('(opencode.ai)', C.dim)}")
    print(f"  {color('✓', C.green)} {color('SSE Streaming', C.pink)} {color('•', C.dim)} {color('Reasoning', C.purple)} {color('•', C.dim)} {color('REST API', C.teal)}")
    print(f"  {color('─' * 52, C.dim)}")

    llm = LLM(config, tools)
    system_content = SYSTEM_PROMPT
    if tool_warning:
        system_content += "\n\n" + tool_warning
    msgs = [{"role": "system", "content": system_content}]

    try:
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
                # Get initial response
                data = llm.chat(msgs)
                msg = data["choices"][0]["message"]

                tool_rounds = 0
                while True:
                    text_content = msg.get("content", "") or ""
                    has_tools = msg.get("tool_calls")

                    if not has_tools:
                        # Pure text response — display directly
                        msgs.append(msg)
                        if text_content.strip():
                            print(f"  {color('AI', C.green)} {color('›', C.green)} ", end="", flush=True)
                            for ch in text_content:
                                print(ch, end="", flush=True)
                                time.sleep(0.008)
                            print()
                        break

                    # Has tool calls — process them
                    process_tool_calls(mcp, msgs, msg)
                    tool_rounds += 1

                    if tool_rounds >= 3:
                        print(f"  {color('AI', C.green)} {color('⟳ wrap up...', C.dim)}", end="\r")
                        sys.stdout.flush()
                        try:
                            data = llm.chat(msgs, force_text=True)
                            next_msg = data["choices"][0]["message"]
                            final_text = next_msg.get("content", "") or ""
                            msgs.append(next_msg)
                            print(" " * 50, end="\r")
                            if final_text.strip():
                                print(f"  {color('AI', C.green)} {color('›', C.green)} ", end="", flush=True)
                                for ch in final_text:
                                    print(ch, end="", flush=True)
                                    time.sleep(0.008)
                                print()
                        except Exception:
                            print(" " * 50, end="\r")
                        break

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

    finally:
        mcp.stop()
        print(f"  {color('MCP server shut down.', C.dim)}")

if __name__ == "__main__":
    main()
