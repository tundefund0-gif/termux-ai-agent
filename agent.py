#!/usr/bin/env python3
"""
Termux AI Agent — DeepSeek V4 Flash (free) + termux-mcp
One command. Does what you say. 103 tools.
"""

import json, os, sys, time, subprocess, socket
from pathlib import Path
import requests

# ─── Config ────────────────────────────────────────────────────────────────
CONFIG_FILE = Path.home() / ".termux-agent.json"
TERMUX_MCP_URL = "http://127.0.0.1:8080"
MCP_DIR = os.path.expanduser("~/termux-mcp")

DEFAULT_CONFIG = {
    "api_key": "",
    "base_url": "https://opencode.ai/zen/v1",
    "model": "deepseek-v4-flash-free",
    "max_tokens": 65536,
    "temperature": 0.7,
    "top_p": 0.95,
    "timeout": 120,
}

def load_config():
    cfg = DEFAULT_CONFIG.copy()
    if CONFIG_FILE.exists():
        try:
            cfg.update(json.loads(CONFIG_FILE.read_text()))
        except:
            pass
    return cfg

# ─── Colors ────────────────────────────────────────────────────────────────
class C:
    reset = "\033[0m"
    bold = "\033[1m"
    dim = "\033[90m"
    green = "\033[32m"
    bgreen = "\033[92m"
    yellow = "\033[93m"
    red = "\033[91m"
    blue = "\033[94m"
    magenta = "\033[95m"
    cyan = "\033[96m"
    white = "\033[97m"

def color(text, c):
    return f"{c}{text}{C.reset}"

# ─── Endpoint map ──────────────────────────────────────────────────────────
ENDPOINT_MAP = {
    "run": "/run", "ls": "/ls", "read": "/read", "write": "/write",
    "mkdir": "/mkdir", "delete": "/delete", "search": "/search",
    "cancel": "/cancel", "diff": "/diff", "patch": "/patch",
    "system_info": "/system-info", "process_list": "/process-list",
    "process_kill": "/process-kill", "health": "/health",
    "cron_add": "/cron-add", "cron_list": "/cron-list", "cron_remove": "/cron-remove",
    "backup": "/backup", "restore": "/restore", "cloud_sync": "/cloud-sync",
    "battery": "/battery", "location": "/location", "wifi_info": "/wifi-info",
    "wifi_scan": "/wifi-scan", "sensor": "/sensor", "fingerprint": "/fingerprint",
    "vibrate": "/vibrate", "torch": "/torch", "brightness": "/brightness",
    "volume": "/volume", "camera_photo": "/camera-photo", "camera_info": "/camera-info",
    "screenshot": "/screenshot", "screen_record": "/screen-record",
    "scan_barcode": "/scan-barcode", "image_process": "/image-process",
    "video_process": "/video-process", "text_extract": "/text-extract",
    "qrcode": "/qrcode", "microphone_record": "/microphone-record",
    "media_player": "/media-player", "wallpaper": "/wallpaper",
    "notify": "/notify", "notify_remove": "/notify-remove", "toast": "/toast",
    "dialog": "/dialog", "share": "/share", "open_url": "/open-url",
    "clipboard_get": "/clipboard-get", "clipboard_set": "/clipboard-set",
    "sms_send": "/sms-send", "sms_inbox": "/sms-inbox", "call": "/call",
    "contacts": "/contacts", "telephony_deviceinfo": "/telephony-deviceinfo",
    "telephony_cellinfo": "/telephony-cellinfo", "tts_speak": "/tts-speak",
    "speech_to_text": "/speech-to-text", "speedtest": "/speedtest",
    "public_ip": "/public-ip", "weather": "/weather", "download": "/download",
    "web_server": "/web-server", "git_op": "/git-op", "git_smart": "/git-smart",
    "git_pr": "/git-pr", "smart_install": "/smart-install", "diagnose": "/diagnose",
    "pkg_smart": "/pkg-smart", "explain": "/explain", "dev_env": "/dev-env",
    "review": "/review", "log_analyze": "/log-analyze", "script_gen": "/script-gen",
    "deps_tree": "/deps-tree", "storage_audit": "/storage-audit",
    "config_fix": "/config-fix", "regex": "/regex", "db_design": "/db-design",
    "db_query": "/db-query", "translate": "/translate", "optimize": "/optimize",
    "profile": "/profile", "error_explain": "/error-explain",
    "permission_fix": "/permission-fix", "tutorial": "/tutorial",
    "history_insight": "/history-insight", "ssh_wizard": "/ssh-wizard",
    "service_guard": "/service-guard", "port_manage": "/port-manage",
    "quick_cmd": "/quick-cmd", "migrate": "/migrate", "recipe_list": "/recipe-list",
    "recipe_run": "/recipe-run", "recipe_save": "/recipe-save", "context": "/context",
    "context_save": "/context-save", "storage_get": "/storage-get",
    "infrared": "/infrared", "list_apps": "/list-apps", "history": "/history",
    "history_save": "/history-save", "history_clear": "/history-clear",
}

PATH_TOOLS = {"write","read","mkdir","delete","search","diff","patch","ls",
    "backup","restore","camera_photo","screenshot","screen_record","qrcode",
    "image_process","video_process","text_extract","wallpaper","download",
    "script_gen","db_query","db_design","storage_get","log_analyze","review",
    "profile","migrate","git_op","git_smart","web_server","speech_to_text"}

# ─── Helpers ───────────────────────────────────────────────────────────────
def expand_path(args, tool_name):
    """Expand ~ in path params for file-based tools."""
    if tool_name not in PATH_TOOLS:
        return args
    args = dict(args)
    home = str(Path.home())
    for k, v in args.items():
        if isinstance(v, str) and "~" in v:
            args[k] = v.replace("~", home)
    return args

# ─── Termux-MCP Client ────────────────────────────────────────────────────
class TermuxMCP:
    def __init__(self):
        self.base = TERMUX_MCP_URL
        self._tools = None

    def ping(self):
        try:
            return requests.get(f"{self.base}/ping", timeout=3).status_code == 200
        except:
            return False

    def get_tools(self):
        if self._tools:
            return self._tools
        try:
            r = requests.get(f"{self.base}/tools", timeout=5)
            if r.status_code == 200:
                self._tools = r.json().get("tools", [])
                return self._tools
        except:
            pass
        return []

    def call(self, tool, args):
        endpoint = ENDPOINT_MAP.get(tool, "/" + tool.replace("_", "-"))
        args = expand_path(args, tool)
        try:
            r = requests.post(f"{self.base}{endpoint}", json=args, timeout=120, stream=True)
            r.raise_for_status()
            if r.headers.get("transfer-encoding") == "chunked":
                out = ""
                for chunk in r.iter_content(chunk_size=None, decode_unicode=True):
                    if chunk:
                        out += chunk
                return out.strip()
            ct = r.headers.get("content-type", "")
            if "json" in ct:
                return json.dumps(r.json(), indent=2)
            return r.text.strip()
        except requests.Timeout:
            return "[Timeout]"
        except requests.HTTPError as e:
            return f"[{e.response.status_code}]" if e.response.status_code != 404 else f"[Unknown tool]"
        except Exception as e:
            return f"[{e}]"

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
        self.timeout = config.get("timeout", 120)

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

        r = requests.post(f"{self.base}/chat/completions", headers=headers, json=body, timeout=self.timeout)
        if r.status_code != 200:
            raise RuntimeError(f"API {r.status_code}: {r.text[:200]}")
        return r.json()

# ─── Server auto-start ─────────────────────────────────────────────────────
def start_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect(("127.0.0.1", 8080))
        s.close()
        return True
    except:
        s.close()

    print(f"  {color('⟳', C.yellow)} {color('Starting termux-mcp...', C.dim)}", end="", flush=True)
    try:
        if os.path.isdir(MCP_DIR):
            subprocess.Popen(
                ["python3", "-m", "termux_mcp"],
                cwd=MCP_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        for _ in range(20):
            time.sleep(0.5)
            print(".", end="", flush=True)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.connect(("127.0.0.1", 8080))
                s.close()
                print(f" {color('✓', C.green)}")
                return True
            except:
                s.close()
        print(f" {color('✖', C.red)}")
        return False
    except Exception as e:
        print(f" {color('✖', C.red)}")
        print(f"  {color(e, C.red)}")
        return False

# ─── Agent ─────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are TermuxAI, an AI assistant controlling an Android phone via Termux.
You have 100+ tools: shell, files, sensors, camera, SMS, calls, GPS, WiFi, git, cron, SSH, media, and more.

RULES:
- Use tools to DO things the user asks — don't just describe what you'd do
- Show results after running commands
- If something fails, try an alternative
- Be concise and helpful"""

BANNER = f"""  {color('┌─────────────────────────────────────────────┐', C.cyan)}
  {color('│', C.cyan)}  {color('⚡ TERMUX AI AGENT', C.bold)} {color('— DeepSeek V4 Flash', C.white)}  {color('│', C.cyan)}
  {color('│', C.cyan)}  {color('× termux-mcp    103 tools', C.magenta)}      {color('│', C.cyan)}
  {color('└─────────────────────────────────────────────┘', C.cyan)}"""

def main():
    config = load_config()
    print(BANNER)

    if not start_server():
        print(f"\n  {color('✖', C.red)} {color('Could not start termux-mcp', C.red)}")
        print(f"  {color('cd ~/termux-mcp && python -m termux_mcp &', C.dim)}")
        sys.exit(1)

    time.sleep(0.3)
    mcp = TermuxMCP()
    tools = mcp.get_tools()
    print(f"  {color('✓', C.green)} {color('termux-mcp', C.cyan)} {color(f'({len(tools)} tools)', C.dim)}")
    print(f"  {color('✓', C.green)} {color('DeepSeek V4 Flash', C.green)} {color('(free)', C.dim)}")
    print(f"  {color('─', C.dim) * 47}\n")

    llm = LLM(config, tools)
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}]

    while True:
        try:
            raw = input(f"  {color('You', C.blue)} {color('›', C.cyan)} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n  {color('Bye!', C.dim)}")
            break

        if not raw:
            continue
        if raw.lower() in ("exit", "quit", "q"):
            print(f"  {color('Bye!', C.dim)}")
            break

        msgs.append({"role": "user", "content": raw})

        for _ in range(20):
            # Show thinking indicator
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

            # Clear thinking line
            print(" " * 50, end="\r")

            # Direct response
            if finish == "stop" or not msg.get("tool_calls"):
                content = msg.get("content", "") or ""
                print(f"  {color('AI', C.green)} {color('›', C.green)} ", end="", flush=True)
                for ch in content:
                    print(ch, end="", flush=True)
                    time.sleep(0.01)
                print()
                break

            # Tool calls
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

        # Keep context manageable
        if len(msgs) > 50:
            keep = [msgs[0]]
            for i in range(len(msgs) - 1, -1, -1):
                if msgs[i]["role"] == "user":
                    keep.append(msgs[i])
                    break
            keep.extend(msgs[-20:])
            msgs = keep

        print(f"  {color('·' * 40, C.dim)}\n")

if __name__ == "__main__":
    main()
