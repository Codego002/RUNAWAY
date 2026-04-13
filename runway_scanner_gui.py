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
        self.root.title("🎬 Runway ML Scanner")
        self.root.geometry("900x650")
        
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
        """Build the interface"""
        
        # ============ TOP BAR ============
        top_frame = ctk.CTkFrame(self.root)
        top_frame.pack(fill="x", padx=10, pady=10)
        
        # Title
        ctk.CTkLabel(
            top_frame,
            text="🎬 Runway ML Scanner",
            font=("Arial", 18, "bold")
        ).pack(side="left", padx=10)
        
        # IP Display
        local_ip = get_local_ip()
        ctk.CTkLabel(
            top_frame,
            text=f"📡 IP: {local_ip}:8080",
            font=("Arial", 12),
            text_color="cyan"
        ).pack(side="left", padx=20)
        
        # Status
        self.status_label = ctk.CTkLabel(
            top_frame,
            text="● Stopped",
            font=("Arial", 14),
            text_color="red"
        )
        self.status_label.pack(side="left", padx=20)
        
        # Buttons
        self.start_btn = ctk.CTkButton(
            top_frame,
            text="▶️  Start",
            command=self.start_scanner,
            width=100,
            height=35,
            fg_color="green"
        )
        self.start_btn.pack(side="right", padx=5)
        
        self.stop_btn = ctk.CTkButton(
            top_frame,
            text="⏹️  Stop",
            command=self.stop_scanner,
            width=100,
            height=35,
            state="disabled",
            fg_color="red"
        )
        self.stop_btn.pack(side="right", padx=5)
        
        # ============ PROXY CONFIG ============
        proxy_frame = ctk.CTkFrame(self.root)
        proxy_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(
            proxy_frame,
            text="🌐 Proxy:",
            font=("Arial", 12, "bold")
        ).pack(side="left", padx=10)
        
        # Proxy checkbox
        self.use_proxy_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            proxy_frame,
            text="Enable",
            variable=self.use_proxy_var
        ).pack(side="left", padx=5)
        
        # Proxy URL
        ctk.CTkLabel(proxy_frame, text="URL:").pack(side="left", padx=5)
        self.proxy_url = ctk.CTkEntry(proxy_frame, width=150, placeholder_text="proxy.example.com")
        self.proxy_url.pack(side="left", padx=2)
        
        # Proxy Port
        ctk.CTkLabel(proxy_frame, text="Port:").pack(side="left", padx=5)
        self.proxy_port = ctk.CTkEntry(proxy_frame, width=50, placeholder_text="8080")
        self.proxy_port.pack(side="left", padx=2)
        
        # Proxy Auth
        ctk.CTkLabel(proxy_frame, text="Auth:").pack(side="left", padx=5)
        self.proxy_auth = ctk.CTkEntry(proxy_frame, width=120, placeholder_text="user:pass")
        self.proxy_auth.pack(side="left", padx=2)
        
        # Save button
        ctk.CTkButton(
            proxy_frame,
            text="💾",
            width=30,
            command=self.save_proxy_config
        ).pack(side="left", padx=5)
        
        # ============ INFO ============
        info_frame = ctk.CTkFrame(self.root)
        info_frame.pack(fill="x", padx=10, pady=5)
        
        info_label = ctk.CTkLabel(
            info_frame,
            text=f"📁 Output: {config.AUTH_FILE}",
            font=("Arial", 11)
        )
        info_label.pack(pady=5)
        
        # Auth status
        self.auth_status = ctk.CTkLabel(
            info_frame,
            text="Auth: Not captured yet",
            font=("Arial", 11)
        )
        self.auth_status.pack(pady=5)
        
        # ============ INSTRUCTIONS ============
        instructions_frame = ctk.CTkFrame(self.root)
        instructions_frame.pack(fill="x", padx=10, pady=5)
        
        instructions = f"""
📝 Instructions:
1. (Optional) Proxy: URL + Port + Auth → Click 💾
2. Click "▶️ Start" → Proxy: {get_local_ip()}:8080
3. Configure browser proxy → {get_local_ip()}:8080
4. Open Runway ML → Auth captured automatically
5. Click "⏹️ Stop" → Done!
        """
        
        ctk.CTkLabel(
            instructions_frame,
            text=instructions,
            font=("Arial", 11),
            justify="left"
        ).pack(padx=10, pady=10)
        
        # ============ LOGS ============
        logs_label = ctk.CTkLabel(
            self.root,
            text="📋 Real-time Logs:",
            font=("Arial", 12, "bold")
        )
        logs_label.pack(anchor="w", padx=10, pady=(10, 5))
        
        # Log textbox
        self.log_text = ctk.CTkTextbox(
            self.root,
            font=("Consolas", 10),
            wrap="word"
        )
        self.log_text.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Clear button
        clear_frame = ctk.CTkFrame(self.root)
        clear_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        ctk.CTkButton(
            clear_frame,
            text="🗑️  Clear Logs",
            command=self.clear_logs,
            width=120
        ).pack(side="right")
    
    def check_auth_status(self):
        """Check if auth file exists and import accounts"""
        if not hasattr(self, "auth_status"):
            return
            
        if config.AUTH_FILE.exists():
            self.auth_status.configure(
                text="Auth: ✅ Found",
                text_color="green"
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
                text="Auth: ❌ Not found - Start scanner",
                text_color="red"
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
        paths = [
            "mitmdump",
            "mitmdump.exe",
            os.path.join(os.getcwd(), "mitmdump.exe"),
            r"C:\Python311\Scripts\mitmdump.exe",
            r"C:\Python310\Scripts\mitmdump.exe",
            r"C:\Python39\Scripts\mitmdump.exe"
        ]
        
        for path in paths:
            if path in ["mitmdump", "mitmdump.exe"]:
                try:
                    subprocess.run([path, "--version"], 
                                 capture_output=True, 
                                 timeout=2)
                    return path
                except:
                    continue
            elif os.path.exists(path):
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
