"""
Runway ML Scanner GUI - FINAL VERSION
Based on Grok research - ALL fixes applied
+ Proxy support
"""
import customtkinter as ctk
import subprocess
import threading
import os
import socket
import sys
import shutil
from pathlib import Path
import queue
import config
import textwrap
import tempfile
import json
import accounts_manager

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


def get_local_ip():
    """Get local IP address"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"


class ScannerGUI:
    def __init__(self):
        """Initialize scanner GUI"""
        self.root = ctk.CTk()
        self.root.title("Runway Scanner")
        self.root.geometry("640x420")
        self.root.minsize(560, 340)
        
        # Scanner state
        self.scanner_process = None
        self.scanner_running = False
        self.temp_script_path = None
        
        # Proxy config file
        self.proxy_config_file = "scanner_proxy_config.json"
        
        # Log queue for thread-safety
        self.log_queue = queue.Queue()
        
        # Build UI FIRST
        self.build_ui()
        
        # Load proxy config
        self.load_proxy_config()
        
        # Check status AFTER
        self.check_auth_status()
    
    def build_ui(self):
        """Compact tool layout: toolbar + proxy row + logs."""
        pad = {"padx": 8, "pady": 6}
        btn = {"height": 28, "corner_radius": 6, "font": ctk.CTkFont(size=12)}
        local_ip = get_local_ip()

        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(3, weight=1)

        top = ctk.CTkFrame(self.root, corner_radius=8, height=40)
        top.grid(row=0, column=0, sticky="ew", **pad)
        top.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(
            top, text="Scanner",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, padx=(10, 8), pady=6)

        ctk.CTkLabel(
            top, text=f"{local_ip}:8080",
            font=ctk.CTkFont(size=12),
            text_color="#4DD0E1"
        ).grid(row=0, column=1, padx=4, pady=6)

        self.status_label = ctk.CTkLabel(
            top, text="● Stopped",
            font=ctk.CTkFont(size=12),
            text_color="#EF5350"
        )
        self.status_label.grid(row=0, column=2, sticky="w", padx=8, pady=6)

        self.stop_btn = ctk.CTkButton(
            top, text="Stop", command=self.stop_scanner,
            width=72, state="disabled",
            fg_color="#C62828", hover_color="#8E0000", **btn
        )
        self.stop_btn.grid(row=0, column=3, padx=4, pady=6)

        self.start_btn = ctk.CTkButton(
            top, text="Start", command=self.start_scanner,
            width=72, fg_color="#2E7D32", hover_color="#1B5E20", **btn
        )
        self.start_btn.grid(row=0, column=4, padx=(4, 10), pady=6)

        proxy = ctk.CTkFrame(self.root, corner_radius=8)
        proxy.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 6))
        proxy.grid_columnconfigure(1, weight=1)

        self.use_proxy_var = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(
            proxy, text="Proxy", variable=self.use_proxy_var,
            width=42, height=22, font=ctk.CTkFont(size=12)
        ).grid(row=0, column=0, padx=(10, 8), pady=6)

        self.proxy_url = ctk.CTkEntry(
            proxy, placeholder_text="host", height=28, width=160
        )
        self.proxy_url.grid(row=0, column=1, padx=3, pady=6, sticky="ew")

        self.proxy_port = ctk.CTkEntry(
            proxy, placeholder_text="port", height=28, width=58
        )
        self.proxy_port.grid(row=0, column=2, padx=3, pady=6)

        self.proxy_auth = ctk.CTkEntry(
            proxy, placeholder_text="user:pass", height=28, width=120
        )
        self.proxy_auth.grid(row=0, column=3, padx=3, pady=6)

        ctk.CTkButton(
            proxy, text="Save", command=self.save_proxy_config,
            width=56, **btn
        ).grid(row=0, column=4, padx=(3, 10), pady=6)

        meta = ctk.CTkFrame(self.root, corner_radius=8, fg_color="transparent")
        meta.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 4))
        meta.grid_columnconfigure(1, weight=1)

        self.auth_status = ctk.CTkLabel(
            meta, text="Auth: none",
            font=ctk.CTkFont(size=11),
            anchor="w"
        )
        self.auth_status.grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            meta, text=str(config.AUTH_FILE),
            font=ctk.CTkFont(size=11),
            text_color="gray70",
            anchor="w"
        ).grid(row=0, column=1, sticky="ew", padx=8)

        ctk.CTkButton(
            meta, text="Clear", command=self.clear_logs,
            width=56, fg_color="transparent", border_width=1, **btn
        ).grid(row=0, column=2, sticky="e")

        self.log_text = ctk.CTkTextbox(
            self.root,
            font=ctk.CTkFont(family="Consolas", size=11),
            wrap="word",
            corner_radius=8
        )
        self.log_text.grid(row=3, column=0, sticky="nsew", padx=8, pady=(0, 8))

        self.add_log(f"Listen {local_ip}:8080  →  mitm.it  →  Runway")
    
    def check_auth_status(self):
        """Check if auth file exists and import accounts"""
        if not hasattr(self, "auth_status"):
            return
            
        if config.AUTH_FILE.exists():
            self.auth_status.configure(
                text="Auth: found",
                text_color="#66BB6A"
            )
            # Auto-import accounts from captured auth file
            try:
                count = accounts_manager.import_from_old_auth_file(str(config.AUTH_FILE))
                if count > 0:
                    self.log_queue.put(f"👤 {count} account(s) extracted → accounts.json")
            except Exception as e:
                print(f"⚠️ Account import error: {e}")
        else:
            self.auth_status.configure(
                text="Auth: none",
                text_color="#EF5350"
            )
    
    def load_proxy_config(self):
        """Load proxy configuration from file"""
        if os.path.exists(self.proxy_config_file):
            try:
                with open(self.proxy_config_file, 'r') as f:
                    config_data = json.load(f)
                    self.use_proxy_var.set(config_data.get('use_proxy', False))
                    self.proxy_url.insert(0, config_data.get('proxy_url', ''))
                    self.proxy_port.insert(0, config_data.get('proxy_port', ''))
                    self.proxy_auth.insert(0, config_data.get('proxy_auth', ''))
            except:
                pass
    
    def save_proxy_config(self):
        """Save proxy configuration to file"""
        config_data = {
            'use_proxy': self.use_proxy_var.get(),
            'proxy_url': self.proxy_url.get(),
            'proxy_port': self.proxy_port.get(),
            'proxy_auth': self.proxy_auth.get()
        }
        with open(self.proxy_config_file, 'w') as f:
            json.dump(config_data, f, indent=2)
        self.add_log("💾 Proxy config saved!")
    
    def find_mitmdump(self):
        """Find mitmdump executable"""
        def is_working_mitmdump(path):
            """Return True if the candidate can execute mitmdump."""
            if not path:
                return False

            try:
                result = subprocess.run(
                    [path, "--version"],
                    capture_output=True,
                    timeout=3,
                    text=True
                )
                output = f"{result.stdout}\n{result.stderr}".lower()
                return result.returncode == 0 and "mitmproxy" in output
            except Exception:
                return False

        candidates = []

        # 1) PATH lookup
        for name in ["mitmdump", "mitmdump.exe"]:
            found = shutil.which(name)
            if found:
                candidates.append(found)

        # 2) Windows lookup
        try:
            where_result = subprocess.run(
                ["where.exe", "mitmdump"],
                capture_output=True,
                timeout=3,
                text=True
            )
            if where_result.returncode == 0:
                for line in where_result.stdout.splitlines():
                    line = line.strip()
                    if line:
                        candidates.append(line)
        except Exception:
            pass

        # 3) Common local locations
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        user_profile = os.environ.get("USERPROFILE", "")
        python_versions = ["Python313", "Python312", "Python311", "Python310", "Python39"]

        candidates.extend([
            os.path.join(os.getcwd(), "mitmdump.exe"),
            os.path.join(program_files, "mitmproxy", "bin", "mitmdump.exe"),
        ])

        for version in python_versions:
            candidates.extend([
                os.path.join(local_appdata, "Programs", "Python", version, "Scripts", "mitmdump.exe"),
                os.path.join(user_profile, "AppData", "Local", "Programs", "Python", version, "Scripts", "mitmdump.exe"),
                os.path.join(r"C:\\", version, "Scripts", "mitmdump.exe"),
            ])

        seen = set()
        for path in candidates:
            normalized = os.path.normcase(path)
            if normalized in seen:
                continue
            seen.add(normalized)

            if os.path.exists(path) and is_working_mitmdump(path):
                return path

        return None
    
    def start_scanner(self):
        """Start mitmdump scanner with ALL Grok fixes"""
        if self.scanner_running:
            return

        mitmdump_path = self.find_mitmdump()
        if not mitmdump_path:
            self.add_log("❌ ERROR: mitmdump not found!")
            self.add_log("Install: pip install mitmproxy")
            return

        # ========================================================
        # GROK FIX #1: EMBEDDED SCRIPT (no external file issues)
        # ========================================================
        addon_script_content = textwrap.dedent("""\
            import json
            import os
            from datetime import datetime
            import sys

            print("="*50, flush=True)
            print("RUNWAY SCANNER STARTED", flush=True)
            print("="*50, flush=True)

            requests_captured = []
            save_counter = 0
            auto_save_interval = 3

            # Get base directory from environment
            base_dir = os.environ.get("RUNWAY_BASE_DIR")
            if not base_dir:
                raise RuntimeError("RUNWAY_BASE_DIR not defined")

            captures_dir = os.path.join(base_dir, "captures")
            os.makedirs(captures_dir, exist_ok=True)

            output_file = os.path.join(captures_dir, "runway_auth.json")
            print(f"OUTPUT: {output_file}", flush=True)
            print("", flush=True)

            def save_data():
                try:
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(requests_captured, f, indent=2, ensure_ascii=False)
                    print(f"SAVED: {len(requests_captured)} requests", flush=True)
                except Exception as e:
                    print(f"ERROR SAVE: {str(e)}", flush=True)

            def request(flow):
                global save_counter
                if "runwayml.com" in flow.request.pretty_host.lower():
                    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    entry = {
                        "timestamp": ts,
                        "method": flow.request.method,
                        "url": flow.request.pretty_url,
                        "path": flow.request.path,
                        "headers": dict(flow.request.headers),
                    }

                    if flow.request.content:
                        try:
                            entry["request_body"] = json.loads(flow.request.content)
                        except:
                            entry["request_body_preview"] = flow.request.content[:500].decode('utf-8', errors='ignore')

                    if "authorization" in flow.request.headers:
                        entry["authorization"] = flow.request.headers["authorization"]

                    requests_captured.append(entry)
                    save_counter += 1
                    
                    print(f"[{ts}] {flow.request.method} {flow.request.path}", flush=True)

                    if save_counter >= auto_save_interval:
                        save_data()
                        save_counter = 0

            def response(flow):
                if "runwayml.com" in flow.request.pretty_host.lower() and flow.response:
                    print(f"  -> Status {flow.response.status_code}", flush=True)
                    if requests_captured:
                        resp_data = {
                            "status": flow.response.status_code,
                            "headers": dict(flow.response.headers),
                        }
                        if flow.response.content:
                            try:
                                resp_data["body"] = json.loads(flow.response.content)
                                print(f"  -> Body captured", flush=True)
                            except:
                                resp_data["body_preview"] = flow.response.content[:500].decode('utf-8', errors='ignore')
                        requests_captured[-1]["response"] = resp_data

            def done():
                if requests_captured:
                    save_data()
                print("", flush=True)
                print("="*50, flush=True)
                print("SCANNER STOPPED", flush=True)
                print("="*50, flush=True)
        """)

        # ========================================================
        # GROK FIX #2: TEMP FILE with dedent (fix indentation)
        # ========================================================
        temp_script = tempfile.NamedTemporaryFile(
            mode='w', 
            suffix='.py', 
            delete=False, 
            encoding='utf-8'
        )
        temp_script.write(addon_script_content)
        temp_script.close()
        self.temp_script_path = temp_script.name

        self.add_log(f"Temp script created: {self.temp_script_path}")

        # ========================================================
        # GROK FIX #3: -q --flow-detail 0 (reduce internal logs)
        # ========================================================
        cmd = [
            mitmdump_path,
            "-s", self.temp_script_path,
            "-q",                  # Quiet mode
            "--flow-detail", "0",  # No flow details
            "--ssl-insecure"
        ]
        
        # PROXY SUPPORT (if enabled)
        if self.use_proxy_var.get():
            url = self.proxy_url.get().strip()
            port = self.proxy_port.get().strip() or "8080"
            auth = self.proxy_auth.get().strip()
            
            if url:
                cmd.extend(["--mode", f"upstream:http://{url}:{port}"])
                if auth:
                    cmd.extend(["--upstream-auth", auth])
                    self.add_log(f"🌐 Proxy: {url}:{port} (with auth)")
                else:
                    self.add_log(f"🌐 Proxy: {url}:{port}")

        # ========================================================
        # GROK FIX #4: Force UTF-8 encoding via environment
        # ========================================================
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["RUNWAY_BASE_DIR"] = os.path.dirname(os.path.abspath(__file__))

        try:
            # Launch subprocess
            if sys.platform == 'win32':
                self.scanner_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    env=env
                )
            else:
                self.scanner_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    env=env
                )

            self.scanner_running = True
            self.status_label.configure(text="● Running", text_color="green")
            self.start_btn.configure(state="disabled")
            self.stop_btn.configure(state="normal")

            self.add_log("")
            self.add_log("="*60)
            self.add_log("🎬 SCANNER STARTED")
            self.add_log("="*60)
            self.add_log(f"📡 Proxy listening: {get_local_ip()}:8080")
            self.add_log(f"📁 Output file: {config.AUTH_FILE}")
            self.add_log(f"🔧 Mitmdump: {mitmdump_path}")
            if self.use_proxy_var.get():
                url = self.proxy_url.get().strip()
                port = self.proxy_port.get().strip() or "8080"
                self.add_log(f"🌐 Upstream proxy: {url}:{port}")
            self.add_log("="*60)
            self.add_log("")

            # ========================================================
            # GROK FIX #7: queue.Queue() for thread-safety
            # ========================================================
            def read_stdout():
                for line in iter(self.scanner_process.stdout.readline, ''):
                    line = line.rstrip()
                    if line:
                        self.log_queue.put(line)

            def read_stderr():
                for line in iter(self.scanner_process.stderr.readline, ''):
                    line = line.rstrip()
                    if line:
                        self.log_queue.put(f"[STDERR] {line}")

            threading.Thread(target=read_stdout, daemon=True).start()
            threading.Thread(target=read_stderr, daemon=True).start()

            # ========================================================
            # GROK FIX #8: process_logs() with after() polling
            # ========================================================
            self.process_logs()

        except Exception as e:
            self.add_log(f"❌ ERROR: {e}")
            # Cleanup temp file on error
            if os.path.exists(self.temp_script_path):
                os.unlink(self.temp_script_path)
    
    def stop_scanner(self):
        """Stop mitmdump scanner"""
        if not self.scanner_running or not self.scanner_process:
            return

        try:
            self.scanner_process.terminate()
            self.scanner_process.wait(timeout=5)
        except:
            try:
                self.scanner_process.kill()
            except:
                pass

        self.scanner_process = None
        self.scanner_running = False
        self.status_label.configure(text="● Stopped", text_color="red")
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

        # Cleanup temp file
        if self.temp_script_path and os.path.exists(self.temp_script_path):
            try:
                os.unlink(self.temp_script_path)
            except:
                pass

        self.log_queue.put("")
        self.log_queue.put("="*60)
        self.log_queue.put("⏹️  SCANNER STOPPED")
        self.log_queue.put("="*60)
        self.log_queue.put(f"📁 Auth saved: {config.AUTH_FILE}")
        self.log_queue.put("="*60)
        self.log_queue.put("")
        
        # Check auth status
        self.check_auth_status()
    
    def add_log(self, message):
        """Add message to log - ONLY called from main thread"""
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
    
    def process_logs(self):
        """Poll the log queue - thread-safe UI updates"""
        try:
            while True:
                message = self.log_queue.get_nowait()
                self.add_log(message)
        except queue.Empty:
            pass
        
        if self.root:
            self.root.after(100, self.process_logs)
    
    def clear_logs(self):
        """Clear log textbox"""
        self.log_text.delete("1.0", "end")
    
    def run(self):
        """Run the application"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.mainloop()
    
    def on_close(self):
        """Cleanup on close"""
        if self.scanner_running:
            self.stop_scanner()
        self.root.destroy()


if __name__ == "__main__":
    app = ScannerGUI()
    app.run()
