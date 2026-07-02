#!/usr/bin/env python3
"""
Termux AI Agent v3.1 — DeepSeek V4 Flash + wujie272/termux-mcp (80 tools)
══════════════════════════════════════════════════════════════════════════
SSE streaming • Reasoning display • Smart Termux:API detection
No infinite loops • Long text • Futuristic UI
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
            "clientInfo": {"name": "termux-ai-agent", "version": "3.1"},
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
            try:
                self.proc.stdin.write(json.dumps(msg) + "\n")
                self.proc.stdin.flush()
            except BrokenPipeError:
                raise  # Let caller handle restart
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
        print(f"  {color('✖', C.red)} Git clone failed.", C.red)
        return False
    for pkg_cmd in [
        ["pip3", "install", "mcp", "requests"],
        ["pip3", "install", "mcp", "requests", "--break-system-packages"],
    ]:
        try:
            subprocess.run(pkg_cmd, capture_output=True)
        except Exception:
            pass
    app_py = Path(MCP_DIR) / "termux_mcp" / "app.py"
    if app_py.exists():
        content = app_py.read_text()
        if "# import termux_mcp.tools.github" in content:
            content = content.replace("# import termux_mcp.tools.github", "import termux_mcp.tools.github")
            app_py.write_text(content)
            print(f"  {color('✓', C.green)} GitHub tools enabled", C.dim)
    return True

# ─── Termux:API Detection ───────────────────────────────────────────────
def probe_termux_api(mcp):
    """Probe Termux:API-dependent tools. Returns warning string or empty."""
    probe_tools = ["get_battery_status", "list_sms"]
    failed_cmds = []
    for tool_name in probe_tools:
        result = mcp.call(tool_name, {})
        if "Command not found: termux-" in result:
            cmd = result.split("Command not found: ")[1].split()[0]
            failed_cmds.append(cmd)

    if failed_cmds:
        return (
            "NOTE: Termux:API is NOT installed (commands not found: "
            + ", ".join(failed_cmds)
            + "). "
            "Tools that require Termux:API will FAIL: get_battery_status, get_location, "
            "get_sensor_list, read_sensor, list_sms, send_sms, text_to_speech, "
            "toggle_torch, vibrate, clipboard, list_contacts, send_notification, "
            "dismiss_notification, list_notifications. "
            "DO NOT call these tools. If you need battery/sensor info, use execute_command "
            "with 'dumpsys' or '/sys/class/power_supply/' commands.\n"
            "IMPORTANT: 'dumpsys' and Android system commands may also fail in Termux "
            "without root. If an execute_command for battery returns empty/no such file, "
            "just tell the user battery info is unavailable — do NOT keep trying new approaches."
        )
    return ""

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
            json=self._payload(messages, stream=True, force_text=False),
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

# ─── Conversation History Management ────────────────────────────────────
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

# ─── User Input ─────────────────────────────────────────────────────────
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

# ─── Streaming Display + Smart Loop Detection ──────────────────────────
def display_streaming_response(mcp, llm, msgs, msg):
    """Display streaming text or process tool calls. Returns True if needs continue."""
    if msg.get("tool_calls"):
        msgs.append(msg)
        termux_api_missing = False
        #
        total_calls = 0

        for tc in msg["tool_calls"]:
            name = tc["function"]["name"]
            total_calls += 1
            try:
                args = json.loads(tc["function"]["arguments"])
            except Exception:
                args = {}
            preview = json.dumps(args)
            if len(preview) > 60:
                preview = preview[:60] + "…"
            print(f"  {color('◆', C.magenta)} {color(name, C.cyan)} {color(preview, C.dim)}", end="", flush=True)

            result = mcp.call(name, args)

            # Smart Termux:API detection
            if "Command not found: termux-" in result:
                termux_api_missing = True
                cmd_name = result.split("Command not found: ")[1].split()[0]
                result += (
                    f"\n\n[SYSTEM: {cmd_name} needs Termux:API which is NOT installed. "
                    f"Do NOT retry this or similar Termux:API tools.]"
                )

            # Track execute_command calls for loop detection
            if name == "execute_command":
                pass  # execcmd tracking removed

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

        # Inject Termux:API guidance if detected
        if termux_api_missing:
            msgs.append({
                "role": "system",
                "content": (
                    "[IMPORTANT] Termux:API is NOT installed. "
                    "Tools needing termux-battery-status, termux-tts-speak, termux-location, "
                    "termux-sms, termux-clipboard, termux-notification, termux-torch, "
                    "termux-vibrate, termux-contact-list, termux-sensor will FAIL. "
                    "DO NOT call them again. Use execute_command with dumpsys/getprop instead."
                )
            })

        print(f"  {color('·' * 40, C.dim)}")
        return True
    else:
        flush_before = ""
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
                msgs.append(data)
        print()
        return False

# ─── System Prompt ──────────────────────────────────────────────────────
BASE_PROMPT = (
    "You are TermuxAI, an AI assistant controlling an Android device via Termux MCP.\n"
    "You have 80 tools: shell commands, file system, UI automation, ADB/Shizuku,\n"
    "app management, communication, device sensors, media, GitHub, and more.\n\n"
    "RULES:\n"
    "- Execute commands immediately when asked\n"
    "- Show clear results after each action\n"
    "- If a tool returns 'Command not found: termux-*', Termux:API is missing.\n"
    "  Do NOT retry that tool or similar ones. Use dumpsys/getprop/sysfs instead.\n"
    "- If you've tried 2+ approaches for something and still failing, stop trying\n"
    "  and tell the user what you found. Don't keep experimenting.\n"
    "- Be concise but thorough. Generate long code/text when asked.\n"
    "- To CREATE files, use execute_command with: python3 -c 'open(\"path\",\"w\").write(\"content\")'\n"
    "  or printf/echo with redirection. NEVER use cat > file or heredoc syntax\n"
    "  in execute_command - it breaks the MCP protocol and causes Broken pipe errors."
)

# ─── Banner ─────────────────────────────────────────────────────────────
BANNER = (
    f"\n"
    f"  {color('╔══════════════════════════════════════════════════╗', C.cyan)}\n"
    f"  {color('║', C.cyan)}  {color('⚡ TERMUX AI AGENT', C.bold)} {color('v3.1', C.dim)}              {color('║', C.cyan)}\n"
    f"  {color('║', C.cyan)}  {color('DeepSeek V4 Flash', C.green)} {color('×', C.dim)} {color('wujie272 MCP', C.magenta)} {color('80 tools', C.dim)} {color('║', C.cyan)}\n"
    f"  {color('║', C.cyan)}  {color('SSE • Reasoning • Smart Loop Detect', C.dim)} {color('║', C.cyan)}\n"
    f"  {color('╚══════════════════════════════════════════════════╝', C.cyan)}"
)

# ─── Main Loop ──────────────────────────────────────────────────────────
def main():
    config = load_config()

    os.system("clear")
    print(BANNER)

    if not install_mcp():
        sys.exit(1)

    print(f"  {color('⟳', C.yellow)} {color('Booting MCP server...', C.dim)}", end="", flush=True)
    mcp = MCP()
    if not mcp.start():
        print(f" {color('✖', C.red)}")
        print(f"  {color('Failed to start termux-mcp', C.red)}")
        sys.exit(1)
    print(f" {color('✓', C.green)}")

    tools = mcp.get_tools()
    print(f"  {color('✓', C.green)} {color('MCP', C.cyan)} {color(f'({len(tools)} tools loaded)', C.dim)}")

    print(f"  {color('⟳', C.yellow)} {color('Checking Termux:API availability...', C.dim)}", end="", flush=True)
    api_warning = probe_termux_api(mcp)
    if api_warning:
        print(f" {color('⚠', C.yellow)}")
        print(f"  {color('⚠', C.yellow)} {color('Termux:API not found', C.dim)}")
        print(f"  {color('⚠', C.yellow)} {color('Battery/location/SMS/TTS disabled', C.dim)}")
        system_prompt = BASE_PROMPT + "\n\n" + api_warning
    else:
        print(f" {color('✓', C.green)}")
        system_prompt = BASE_PROMPT

    print(f"  {color('✓', C.green)} {color('DeepSeek V4 Flash', C.green)} {color('(opencode.ai)', C.dim)}")
    print(f"  {color('✓', C.green)} {color('SSE Streaming', C.pink)} {color('•', C.dim)} {color('Reasoning', C.purple)} {color('•', C.dim)} {color('Smart Loop Detect', C.teal)}")
    print(f"  {color('─' * 52, C.dim)}")

    llm = LLM(config, tools)
    msgs = [{"role": "system", "content": system_prompt}]

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
            data = llm.chat(msgs)
            choice = data["choices"][0]
            msg = choice["message"]

            tool_rounds = 0
            while True:
                needs_continue = display_streaming_response(mcp, llm, msgs, msg)
                if not needs_continue:
                    break
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
                        print(f"  {color('AI', C.green)} {color('›', C.green)} ", end="", flush=True)
                        for ch in final_text:
                            print(ch, end="", flush=True)
                            time.sleep(0.008)
                        print()
                    except Exception as e:
                        print(" " * 50, end="\r")
                        print(f"  {color('✖', C.red)} {color(str(e)[:120], C.red)}")
                    break
                print(f"  {color('AI', C.green)} {color('⟳ follow-up...', C.dim)}", end="\r")
                sys.stdout.flush()
                data = llm.chat(msgs)
                msg = data["choices"][0]["message"]
                print(" " * 50, end="\r")

            msgs = trim_history(msgs)

        except (BrokenPipeError, ConnectionError, OSError) as e:
            print(" " * 50, end="\r")
            print(f"  {color('✖ MCP Error:', C.red)} {color(str(e)[:120], C.red)}")
            print(f"  {color('⟳', C.yellow)} {color('Restarting MCP server...', C.dim)}", end="", flush=True)
            mcp.stop()
            time.sleep(0.5)
            if mcp.start():
                print(f" {color('✓', C.green)}")
                # Re-fetch tools
                tools = mcp.get_tools()
                llm.tools = tools
                msgs.append({"role": "system", "content": "MCP server was restarted due to a broken pipe. Avoid using heredoc/cat > in execute_command."})
            else:
                print(f" {color('✖', C.red)}")
                print(f"  {color('Failed to restart MCP server', C.red)}")
        except Exception as e:
            print(" " * 50, end="\r")
            print(f"  {color('✖ Error:', C.red)} {color(str(e)[:200], C.red)}")

        print(f"  {color('─' * 52, C.dim)}")

    mcp.stop()
    print(f"  {color('MCP server shut down.', C.dim)}")

if __name__ == "__main__":
    main()
