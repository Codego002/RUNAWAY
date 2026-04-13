"""
account_manager.py
GUI Manager pour gerer les identites et comptes Fruitz
VERSION CORRIGEE avec support proxy upstream
"""
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import json
import os
import subprocess
import threading
import socket
from datetime import datetime
import sys

# === CONFIGURATION ===
IDENTITIES_DIR = "identities"
ACTIVE_IDENTITY_FILE = os.path.join(IDENTITIES_DIR, "active_identity.json")
CAPTURED_DIR = "captured_accounts"
ACTIVE_SESSION_FILE = "active_session.json"
PROXY_CONFIG_FILE = "proxy_config.json"

os.makedirs(IDENTITIES_DIR, exist_ok=True)
os.makedirs(CAPTURED_DIR, exist_ok=True)

# === COULEURS ===
BG_MAIN = "#1a1a2e"
BG_SECONDARY = "#16213e"
BG_TERTIARY = "#0f3460"
TEXT_PRIMARY = "#ffffff"
TEXT_SECONDARY = "#a0a0a0"
ACCENT = "#e94560"
ACCENT2 = "#00d9ff"
SUCCESS = "#00ff88"
WARNING = "#ffaa00"


def get_local_ip():
    """Recupere l'IP locale"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"


class ProxyConfig:
    """Gestion de la configuration proxy"""
    
    @staticmethod
    def load() -> dict:
        if os.path.exists(PROXY_CONFIG_FILE):
            try:
                with open(PROXY_CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {
            "upstream_enabled": True,
            "upstream_url": "pronice2.ddns.net",
            "upstream_port": 8043,
            "upstream_auth": "223541dd:a2d6496dfa",
            "listen_port": 8080
        }
    
    @staticmethod
    def save(config: dict):
        with open(PROXY_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)


class AccountManager(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self.title("Fruitz Account Manager")
        self.geometry("950x750")
        self.configure(bg=BG_MAIN)
        
        # Variables
        self.proxy_process = None
        self.proxy_running = False
        self.proxy_config = ProxyConfig.load()
        
        # Setup GUI
        self._setup_gui()
        
        # Charger donnees
        self.refresh_identities()
        self.refresh_accounts()
    
    def _setup_gui(self):
        """Configuration interface"""
        # Titre
        title = tk.Label(self, text="Fruitz Account Manager", 
                        font=("Segoe UI", 20, "bold"), 
                        bg=BG_MAIN, fg=ACCENT)
        title.pack(pady=10)
        
        # Notebook (onglets)
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TNotebook', background=BG_MAIN)
        style.configure('TNotebook.Tab', background=BG_SECONDARY, 
                       foreground=TEXT_PRIMARY, padding=[15, 5])
        style.map('TNotebook.Tab', background=[('selected', BG_TERTIARY)])
        
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Onglet 1: Identites
        self.tab_identities = tk.Frame(self.notebook, bg=BG_SECONDARY)
        self.notebook.add(self.tab_identities, text="Identites")
        self._setup_identities_tab()
        
        # Onglet 2: Comptes captures
        self.tab_accounts = tk.Frame(self.notebook, bg=BG_SECONDARY)
        self.notebook.add(self.tab_accounts, text="Comptes")
        self._setup_accounts_tab()
        
        # Onglet 3: Proxy
        self.tab_proxy = tk.Frame(self.notebook, bg=BG_SECONDARY)
        self.notebook.add(self.tab_proxy, text="Proxy")
        self._setup_proxy_tab()
    
    def _setup_identities_tab(self):
        """Onglet gestion des identites"""
        # Boutons haut
        btn_frame = tk.Frame(self.tab_identities, bg=BG_SECONDARY)
        btn_frame.pack(fill='x', padx=10, pady=10)
        
        tk.Button(btn_frame, text="[+] Nouvelle Identite", 
                 command=self.create_identity_dialog,
                 bg=SUCCESS, fg="black", font=("Segoe UI", 10, "bold"),
                 width=18).pack(side='left', padx=5)
        
        tk.Button(btn_frame, text="[*] Generation Rapide",
                 command=self.quick_generate,
                 bg=ACCENT2, fg="black", font=("Segoe UI", 10, "bold"),
                 width=18).pack(side='left', padx=5)
        
        tk.Button(btn_frame, text="Rafraichir",
                 command=self.refresh_identities,
                 bg=BG_TERTIARY, fg=TEXT_PRIMARY, font=("Segoe UI", 10),
                 width=12).pack(side='right', padx=5)
        
        # Liste
        list_frame = tk.Frame(self.tab_identities, bg=BG_SECONDARY)
        list_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        columns = ("nom", "status", "device_id", "location", "date")
        self.identity_tree = ttk.Treeview(list_frame, columns=columns, 
                                          show='headings', height=12)
        
        self.identity_tree.heading("nom", text="Nom")
        self.identity_tree.heading("status", text="Statut")
        self.identity_tree.heading("device_id", text="Device ID")
        self.identity_tree.heading("location", text="Location")
        self.identity_tree.heading("date", text="Cree le")
        
        self.identity_tree.column("nom", width=100)
        self.identity_tree.column("status", width=80)
        self.identity_tree.column("device_id", width=250)
        self.identity_tree.column("location", width=150)
        self.identity_tree.column("date", width=120)
        
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", 
                                  command=self.identity_tree.yview)
        self.identity_tree.configure(yscrollcommand=scrollbar.set)
        
        self.identity_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Boutons action
        action_frame = tk.Frame(self.tab_identities, bg=BG_SECONDARY)
        action_frame.pack(fill='x', padx=10, pady=10)
        
        tk.Button(action_frame, text="[OK] Activer",
                 command=self.activate_identity,
                 bg=SUCCESS, fg="black", font=("Segoe UI", 10, "bold"),
                 width=12).pack(side='left', padx=5)
        
        tk.Button(action_frame, text="Details",
                 command=self.show_identity_details,
                 bg=BG_TERTIARY, fg=TEXT_PRIMARY, font=("Segoe UI", 10),
                 width=12).pack(side='left', padx=5)
        
        tk.Button(action_frame, text="Supprimer",
                 command=self.delete_identity,
                 bg=ACCENT, fg=TEXT_PRIMARY, font=("Segoe UI", 10),
                 width=12).pack(side='left', padx=5)
    
    def _setup_accounts_tab(self):
        """Onglet comptes captures"""
        # Boutons haut
        btn_frame = tk.Frame(self.tab_accounts, bg=BG_SECONDARY)
        btn_frame.pack(fill='x', padx=10, pady=10)
        
        tk.Button(btn_frame, text="Rafraichir",
                 command=self.refresh_accounts,
                 bg=BG_TERTIARY, fg=TEXT_PRIMARY, font=("Segoe UI", 10),
                 width=12).pack(side='right', padx=5)
        
        # Liste
        list_frame = tk.Frame(self.tab_accounts, bg=BG_SECONDARY)
        list_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        columns = ("user_id", "email", "status", "location", "date")
        self.account_tree = ttk.Treeview(list_frame, columns=columns,
                                         show='headings', height=12)
        
        self.account_tree.heading("user_id", text="User ID")
        self.account_tree.heading("email", text="Email")
        self.account_tree.heading("status", text="Statut")
        self.account_tree.heading("location", text="Location")
        self.account_tree.heading("date", text="Capture le")
        
        self.account_tree.column("user_id", width=200)
        self.account_tree.column("email", width=200)
        self.account_tree.column("status", width=80)
        self.account_tree.column("location", width=150)
        self.account_tree.column("date", width=120)
        
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical",
                                  command=self.account_tree.yview)
        self.account_tree.configure(yscrollcommand=scrollbar.set)
        
        self.account_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Boutons action
        action_frame = tk.Frame(self.tab_accounts, bg=BG_SECONDARY)
        action_frame.pack(fill='x', padx=10, pady=10)
        
        tk.Button(action_frame, text="[OK] Activer (Injection)",
                 command=self.activate_account,
                 bg=SUCCESS, fg="black", font=("Segoe UI", 10, "bold"),
                 width=18).pack(side='left', padx=5)
        
        tk.Button(action_frame, text="Details",
                 command=self.show_account_details,
                 bg=BG_TERTIARY, fg=TEXT_PRIMARY, font=("Segoe UI", 10),
                 width=12).pack(side='left', padx=5)
        
        tk.Button(action_frame, text="Exporter",
                 command=self.export_account,
                 bg=ACCENT2, fg="black", font=("Segoe UI", 10),
                 width=12).pack(side='left', padx=5)
    
    def _setup_proxy_tab(self):
        """Onglet configuration proxy"""
        # IP Info
        info_frame = tk.Frame(self.tab_proxy, bg=BG_TERTIARY)
        info_frame.pack(fill='x', padx=10, pady=10)
        
        local_ip = get_local_ip()
        
        tk.Label(info_frame, text="Configuration iPhone:",
                bg=BG_TERTIARY, fg=ACCENT2, 
                font=("Segoe UI", 12, "bold")).pack(anchor='w', padx=10, pady=5)
        
        self.ip_label = tk.Label(info_frame, 
                                text=f"Proxy: {local_ip}:{self.proxy_config.get('listen_port', 8080)}",
                                bg=BG_TERTIARY, fg=SUCCESS,
                                font=("Consolas", 14, "bold"))
        self.ip_label.pack(anchor='w', padx=10, pady=5)
        
        tk.Label(info_frame, 
                text=f"Certificat: http://{local_ip}:{self.proxy_config.get('listen_port', 8080)}/mitm.ca",
                bg=BG_TERTIARY, fg=TEXT_SECONDARY,
                font=("Consolas", 10)).pack(anchor='w', padx=10, pady=2)
        
        # Configuration Upstream
        upstream_frame = tk.LabelFrame(self.tab_proxy, text="Proxy Upstream (Rotation IP)",
                                       bg=BG_SECONDARY, fg=TEXT_PRIMARY,
                                       font=("Segoe UI", 10, "bold"))
        upstream_frame.pack(fill='x', padx=10, pady=10)
        
        # Checkbox activer upstream
        self.upstream_var = tk.BooleanVar(value=self.proxy_config.get("upstream_enabled", True))
        tk.Checkbutton(upstream_frame, text="Utiliser proxy upstream",
                      variable=self.upstream_var,
                      bg=BG_SECONDARY, fg=TEXT_PRIMARY, selectcolor=BG_TERTIARY,
                      font=("Segoe UI", 10),
                      command=self.save_proxy_config).pack(anchor='w', padx=10, pady=5)
        
        # URL
        url_frame = tk.Frame(upstream_frame, bg=BG_SECONDARY)
        url_frame.pack(fill='x', padx=10, pady=5)
        
        tk.Label(url_frame, text="URL:", bg=BG_SECONDARY, fg=TEXT_PRIMARY,
                font=("Segoe UI", 10), width=8, anchor='w').pack(side='left')
        
        self.upstream_url = tk.Entry(url_frame, width=30, font=("Consolas", 10))
        self.upstream_url.insert(0, self.proxy_config.get("upstream_url", ""))
        self.upstream_url.pack(side='left', padx=5)
        
        tk.Label(url_frame, text="Port:", bg=BG_SECONDARY, fg=TEXT_PRIMARY,
                font=("Segoe UI", 10)).pack(side='left', padx=(10, 5))
        
        self.upstream_port = tk.Entry(url_frame, width=6, font=("Consolas", 10))
        self.upstream_port.insert(0, str(self.proxy_config.get("upstream_port", 8043)))
        self.upstream_port.pack(side='left')
        
        # Auth
        auth_frame = tk.Frame(upstream_frame, bg=BG_SECONDARY)
        auth_frame.pack(fill='x', padx=10, pady=5)
        
        tk.Label(auth_frame, text="Auth:", bg=BG_SECONDARY, fg=TEXT_PRIMARY,
                font=("Segoe UI", 10), width=8, anchor='w').pack(side='left')
        
        self.upstream_auth = tk.Entry(auth_frame, width=40, font=("Consolas", 10))
        self.upstream_auth.insert(0, self.proxy_config.get("upstream_auth", ""))
        self.upstream_auth.pack(side='left', padx=5)
        
        tk.Label(auth_frame, text="(user:pass)", bg=BG_SECONDARY, fg=TEXT_SECONDARY,
                font=("Segoe UI", 9)).pack(side='left', padx=5)
        
        # Bouton sauvegarder config
        tk.Button(upstream_frame, text="Sauvegarder Config",
                 command=self.save_proxy_config,
                 bg=ACCENT2, fg="black", font=("Segoe UI", 10),
                 width=18).pack(pady=10)
        
        # === MODE INJECTION ===
        mode_frame = tk.LabelFrame(self.tab_proxy, text="Mode Injection",
                                   bg=BG_SECONDARY, fg=TEXT_PRIMARY,
                                   font=("Segoe UI", 10, "bold"))
        mode_frame.pack(fill='x', padx=10, pady=10)
        
        # Frame pour les boutons radio horizontaux
        radio_frame = tk.Frame(mode_frame, bg=BG_SECONDARY)
        radio_frame.pack(fill='x', padx=10, pady=5)
        
        self.injection_mode_var = tk.StringVar(value=self.proxy_config.get("injection_mode", "creation"))
        
        tk.Radiobutton(radio_frame, text="Creation (nouvelle identite)", 
                      variable=self.injection_mode_var, value="creation",
                      bg=BG_SECONDARY, fg=TEXT_PRIMARY, selectcolor=BG_TERTIARY,
                      font=("Segoe UI", 10), command=self.save_proxy_config).pack(side='left', padx=10)
        
        tk.Radiobutton(radio_frame, text="Connexion (compte existant)", 
                      variable=self.injection_mode_var, value="connexion",
                      bg=BG_SECONDARY, fg=TEXT_PRIMARY, selectcolor=BG_TERTIARY,
                      font=("Segoe UI", 10), command=self.save_proxy_config).pack(side='left', padx=10)
        
        # Checkbox Force Logout
        self.force_logout_var = tk.BooleanVar(value=self.proxy_config.get("force_logout", False))
        tk.Checkbutton(mode_frame, text="Force Logout (soft reset - experimental)",
                      variable=self.force_logout_var,
                      bg=BG_SECONDARY, fg="#ff9800", selectcolor=BG_TERTIARY,
                      font=("Segoe UI", 10),
                      command=self.save_proxy_config).pack(anchor='w', padx=20, pady=5)
        
        # Checkbox Remove Ban
        self.remove_ban_var = tk.BooleanVar(value=self.proxy_config.get("remove_ban", False))
        tk.Checkbutton(mode_frame, text="Remove Ban (retire le ban des reponses)",
                      variable=self.remove_ban_var,
                      bg=BG_SECONDARY, fg="#4caf50", selectcolor=BG_TERTIARY,
                      font=("Segoe UI", 10),
                      command=self.save_proxy_config).pack(anchor='w', padx=20, pady=2)



        # Boutons controle
        control_frame = tk.Frame(self.tab_proxy, bg=BG_SECONDARY)
        control_frame.pack(fill='x', padx=10, pady=10)
        
        self.btn_start = tk.Button(control_frame, text="[>] Demarrer Proxy",
                                   command=self.start_proxy,
                                   bg=SUCCESS, fg="black",
                                   font=("Segoe UI", 12, "bold"),
                                   width=20, height=2)
        self.btn_start.pack(side='left', padx=10)
        
        self.btn_stop = tk.Button(control_frame, text="[X] Arreter Proxy",
                                  command=self.stop_proxy,
                                  bg=ACCENT, fg=TEXT_PRIMARY,
                                  font=("Segoe UI", 12, "bold"),
                                  width=20, height=2,
                                  state='disabled')
        self.btn_stop.pack(side='left', padx=10)
        
        # Status
        self.proxy_status = tk.Label(self.tab_proxy, text="Proxy arrete",
                                    bg=BG_SECONDARY, fg=ACCENT,
                                    font=("Segoe UI", 12, "bold"))
        self.proxy_status.pack(pady=10)
        
        # Logs
        tk.Label(self.tab_proxy, text="Logs:", bg=BG_SECONDARY, 
                fg=TEXT_PRIMARY, font=("Segoe UI", 10, "bold")).pack(anchor='w', padx=10)
        
        self.log_text = scrolledtext.ScrolledText(self.tab_proxy, height=12,
                                                  bg="#0a0a15", fg=SUCCESS,
                                                  font=("Consolas", 9))
        self.log_text.pack(fill='both', expand=True, padx=10, pady=5)
        self.log_text.config(state='disabled')
    
    def log(self, message):
        """Ajoute un message aux logs"""
        self.log_text.config(state='normal')
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert('end', f"[{timestamp}] {message}\n")
        self.log_text.see('end')
        self.log_text.config(state='disabled')
    
    def save_proxy_config(self):
        """Sauvegarde la configuration proxy"""
        self.proxy_config = {
            "upstream_enabled": self.upstream_var.get(),
            "upstream_url": self.upstream_url.get().strip(),
            "upstream_port": int(self.upstream_port.get().strip() or 8043),
            "upstream_auth": self.upstream_auth.get().strip(),
            "listen_port": 8080,
            "injection_mode": self.injection_mode_var.get(),
            "force_logout": self.force_logout_var.get(),
            "remove_ban": self.remove_ban_var.get()
        }
        ProxyConfig.save(self.proxy_config)
        mode_str = self.injection_mode_var.get()
        if self.force_logout_var.get():
            mode_str += " + LOGOUT"
        if self.remove_ban_var.get():
            mode_str += " + UNBAN"
        self.log(f"Config: {mode_str}")
    
    def start_proxy(self):
        """Demarre le proxy mitmproxy"""
        if self.proxy_running:
            return
        
        # Sauvegarder config d'abord
        self.save_proxy_config()
        
        # Trouver mitmdump
        mitmdump_paths = [
            "mitmdump",
            "mitmdump.exe",
            os.path.join(os.getcwd(), "mitmdump.exe"),
            r"C:\Python311\Scripts\mitmdump.exe",
            r"C:\Python310\Scripts\mitmdump.exe"
        ]
        
        mitmdump_path = None
        for path in mitmdump_paths:
            if os.path.exists(path) or path == "mitmdump":
                mitmdump_path = path
                break
        
        if not mitmdump_path:
            messagebox.showerror("Erreur", "mitmdump non trouve!\nInstallez mitmproxy: pip install mitmproxy")
            return
        
        # Script A  utiliser
        script_path = "runway_scanner.py"
        if not os.path.exists(script_path):
            messagebox.showerror("Erreur", f"Script non trouve: {script_path}")
            return
        
        # Construire la commande
        cmd = [mitmdump_path, "-s", script_path]
        
        # Ajouter upstream si active
        if self.proxy_config.get("upstream_enabled"):
            url = self.proxy_config.get("upstream_url", "")
            port = self.proxy_config.get("upstream_port", 8043)
            auth = self.proxy_config.get("upstream_auth", "")
            
            if url:
                cmd.extend(["--mode", f"upstream:http://{url}:{port}"])
                if auth:
                    cmd.extend(["--upstream-auth", auth])
        
        # Ajouter options standard
        cmd.extend([
            "--ssl-insecure",
            "-p", str(self.proxy_config.get("listen_port", 8080))
        ])
        
        self.log(f"Commande: {' '.join(cmd)}")
        
        # Lancer le process
        try:
            # Windows: CREATE_NO_WINDOW pour cacher la console
            if sys.platform == 'win32':
                self.proxy_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            else:
                self.proxy_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
            
            self.proxy_running = True
            self.btn_start.config(state='disabled')
            self.btn_stop.config(state='normal')
            self.proxy_status.config(text="Proxy en cours", fg=SUCCESS)
            
            # Thread pour lire stdout
            def read_output():
                try:
                    if self.proxy_process and self.proxy_process.stdout:
                        for line in self.proxy_process.stdout:
                            line = line.strip()
                            if line:
                                self.after(0, lambda l=line: self.log(l))
                except:
                    pass
            
            threading.Thread(target=read_output, daemon=True).start()
            
            self.log("[OK] Proxy demarre!")
            
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de lancer le proxy:\n{e}")
            self.proxy_running = False
    
    def stop_proxy(self):
        """Arrete le proxy"""
        if self.proxy_process:
            try:
                self.proxy_process.terminate()
                self.proxy_process.wait(timeout=3)
            except:
                try:
                    self.proxy_process.kill()
                except:
                    pass
            
            self.proxy_process = None
        
        self.proxy_running = False
        self.btn_start.config(state='normal')
        self.btn_stop.config(state='disabled')
        self.proxy_status.config(text="Proxy arrete", fg=ACCENT)
        self.log("Proxy arrete")
    
    def refresh_identities(self):
        """Rafraichit la liste des identites"""
        # Effacer
        for item in self.identity_tree.get_children():
            self.identity_tree.delete(item)
        
        # Charger
        if os.path.exists(IDENTITIES_DIR):
            for filename in sorted(os.listdir(IDENTITIES_DIR)):
                if filename.endswith('.json'):
                    filepath = os.path.join(IDENTITIES_DIR, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        
                        # Device ID: dans fruitz ou mixpanel ou racine
                        fruitz = data.get('fruitz', {})
                        mixpanel = data.get('mixpanel', {})
                        device_id = fruitz.get('x-fruitz-deviceid') or mixpanel.get('device_id') or data.get('device_id', 'N/A')
                        device_display = f"{device_id[:25]}..." if device_id and len(device_id) > 25 else device_id
                        
                        # Location: ville ou city
                        loc = data.get('location', {})
                        city = loc.get('ville') or loc.get('city', 'N/A')
                        
                        # Date
                        created_at = data.get('created_at', '')
                        date_display = created_at[:10] if created_at else 'N/A'
                        
                        self.identity_tree.insert('', 'end', values=(
                            data.get('name', 'N/A'),
                            data.get('status', 'new'),
                            device_display,
                            city,
                            date_display
                        ), tags=(filename,))
                    except:
                        continue
    
    def refresh_accounts(self):
        """Rafraichit la liste des comptes"""
        # Effacer
        for item in self.account_tree.get_children():
            self.account_tree.delete(item)
        
        # Charger
        if os.path.exists(CAPTURED_DIR):
            for filename in sorted(os.listdir(CAPTURED_DIR), reverse=True):
                if filename.endswith('.json'):
                    filepath = os.path.join(CAPTURED_DIR, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        
                        # User ID: directement ou dans fruitz
                        user_id = data.get('user_id') or data.get('fruitz', {}).get('user_id', 'N/A')
                        user_id_display = f"{user_id[:25]}..." if user_id and len(user_id) > 25 else user_id
                        
                        # Email
                        email = data.get('email', 'N/A')
                        
                        # Status: actif par defaut
                        status = data.get('status', 'actif')
                        
                        # Location: dans identity_used ou location
                        identity_used = data.get('identity_used', {})
                        loc = identity_used.get('location', {}) or data.get('location', {})
                        city = loc.get('city') or loc.get('ville', 'N/A')
                        
                        # Date
                        captured_at = data.get('captured_at', '')
                        date_display = captured_at[:10] if captured_at else 'N/A'
                        
                        self.account_tree.insert('', 'end', values=(
                            user_id_display,
                            email,
                            status,
                            city,
                            date_display
                        ), tags=(filename,))
                    except:
                        continue
    
    def create_identity_dialog(self):
        """Dialogue creation identite"""
        from identity_generator import FruitzIdentityGenerator
        
        dialog = tk.Toplevel(self)
        dialog.title("Nouvelle Identite")
        dialog.geometry("450x500")
        dialog.configure(bg=BG_SECONDARY)
        dialog.transient(self)
        dialog.grab_set()
        
        # Champs
        tk.Label(dialog, text="Nom de l'identite:", bg=BG_SECONDARY, 
                fg=TEXT_PRIMARY, font=("Segoe UI", 10)).pack(anchor='w', padx=20, pady=(20,5))
        name_entry = tk.Entry(dialog, width=40, font=("Segoe UI", 10))
        name_entry.pack(padx=20, pady=5)
        name_entry.insert(0, "Nouveau Compte")
        
        tk.Label(dialog, text="Timezone:", bg=BG_SECONDARY,
                fg=TEXT_PRIMARY, font=("Segoe UI", 10)).pack(anchor='w', padx=20, pady=(15,5))
        
        timezones = ["Europe/Paris", "Europe/London", "America/New_York", 
                    "America/Los_Angeles", "America/Chicago"]
        tz_var = tk.StringVar(value="Europe/Paris")
        tz_combo = ttk.Combobox(dialog, textvariable=tz_var, values=timezones, 
                               state='readonly', width=37)
        tz_combo.pack(padx=20, pady=5)
        
        tk.Label(dialog, text="Localisation:", bg=BG_SECONDARY,
                fg=TEXT_PRIMARY, font=("Segoe UI", 10, "bold")).pack(anchor='w', padx=20, pady=(15,5))
        
        loc_frame = tk.Frame(dialog, bg=BG_SECONDARY)
        loc_frame.pack(fill='x', padx=20, pady=5)
        
        tk.Label(loc_frame, text="Lat:", bg=BG_SECONDARY, fg=TEXT_PRIMARY).pack(side='left')
        lat_entry = tk.Entry(loc_frame, width=12, font=("Segoe UI", 10))
        lat_entry.pack(side='left', padx=5)
        lat_entry.insert(0, "48.8566")
        
        tk.Label(loc_frame, text="Lon:", bg=BG_SECONDARY, fg=TEXT_PRIMARY).pack(side='left', padx=(10,0))
        lon_entry = tk.Entry(loc_frame, width=12, font=("Segoe UI", 10))
        lon_entry.pack(side='left', padx=5)
        lon_entry.insert(0, "2.3522")
        
        tk.Label(dialog, text="Ville:", bg=BG_SECONDARY, fg=TEXT_PRIMARY).pack(anchor='w', padx=20, pady=(10,5))
        ville_entry = tk.Entry(dialog, width=40, font=("Segoe UI", 10))
        ville_entry.pack(padx=20, pady=5)
        ville_entry.insert(0, "Paris")
        
        tk.Label(dialog, text="Modele iPhone:", bg=BG_SECONDARY,
                fg=TEXT_PRIMARY, font=("Segoe UI", 10)).pack(anchor='w', padx=20, pady=(15,5))
        
        models = ["iPhone 12", "iPhone 12 Pro", "iPhone 13", "iPhone 13 Pro", 
                 "iPhone 14", "iPhone 14 Pro", "iPhone 15", "iPhone 15 Pro Max"]
        model_var = tk.StringVar(value="iPhone 15 Pro Max")
        model_combo = ttk.Combobox(dialog, textvariable=model_var, values=models,
                                  state='readonly', width=37)
        model_combo.pack(padx=20, pady=5)
        
        def create():
            gen = FruitzIdentityGenerator()
            location = {
                "lat": float(lat_entry.get()),
                "lon": float(lon_entry.get()),
                "ville": ville_entry.get().strip()
            }
            identity = gen.generate_full_identity(
                name=name_entry.get().strip(),
                timezone=tz_var.get(),
                location=location
            )
            gen.save_identity(identity)
            
            messagebox.showinfo("Succes", f"Identite creee: {identity['identity_id'][:8]}...")
            dialog.destroy()
            self.refresh_identities()
        
        tk.Button(dialog, text="[OK] Creer", command=create,
                 bg=SUCCESS, fg="black", font=("Segoe UI", 11, "bold"),
                 width=15).pack(pady=30)
    
    def quick_generate(self):
        """Generation rapide d'identite"""
        from identity_generator import FruitzIdentityGenerator

        gen = FruitzIdentityGenerator()
        identity = gen.generate_full_identity(name=f"Compte_{datetime.now().strftime('%H%M%S')}")
        gen.save_identity(identity)
        
        self.log(f"[OK] Identite generee: {identity['identity_id'][:8]}...")
        self.refresh_identities()
    
    def activate_identity(self):
        """Active l'identite selectionnee"""
        selection = self.identity_tree.selection()
        if not selection:
            messagebox.showwarning("Attention", "Selectionnez une identite")
            return
        
        item = selection[0]
        filename = self.identity_tree.item(item, 'tags')[0]
        filepath = os.path.join(IDENTITIES_DIR, filename)
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                identity = json.load(f)
            
            # ACTIVER l'identite
            identity["status"] = "active"
            
            # Copier vers active_identity.json
            with open(ACTIVE_IDENTITY_FILE, 'w', encoding='utf-8') as f:
                json.dump(identity, f, indent=2, ensure_ascii=False)
            
            messagebox.showinfo("Succes", 
                f"Identite activee: {identity.get('name')}\n\n"
                f"Device: {identity.get('fruitz', {}).get('x-fruitz-deviceid', 'N/A')[:20]}...\n"
                f"Location: {identity.get('location', {}).get('ville', 'N/A')}")
            
            self.log(f"[OK] Identite activee: {identity.get('name')}")
            
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur: {e}")
    
    def show_identity_details(self):
        """Affiche les details d'une identite"""
        selection = self.identity_tree.selection()
        if not selection:
            messagebox.showwarning("Attention", "Selectionnez une identite")
            return
        
        item = selection[0]
        filename = self.identity_tree.item(item, 'tags')[0]
        filepath = os.path.join(IDENTITIES_DIR, filename)
        
        self._show_json_dialog("Details Identite", filepath)
    
    def delete_identity(self):
        """Supprime une identite"""
        selection = self.identity_tree.selection()
        if not selection:
            messagebox.showwarning("Attention", "Selectionnez une identite")
            return
        
        if not messagebox.askyesno("Confirmation", "Supprimer cette identite?"):
            return
        
        item = selection[0]
        filename = self.identity_tree.item(item, 'tags')[0]
        filepath = os.path.join(IDENTITIES_DIR, filename)
        
        try:
            os.remove(filepath)
            self.refresh_identities()
            self.log(f"Identite supprimee: {filename}")
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur: {e}")
    
    def activate_account(self):
        """Active un compte pour injection"""
        selection = self.account_tree.selection()
        if not selection:
            messagebox.showwarning("Attention", "Selectionnez un compte")
            return
        
        item = selection[0]
        filename = self.account_tree.item(item, 'tags')[0]
        filepath = os.path.join(CAPTURED_DIR, filename)
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                account = json.load(f)
            
            # Copier vers active_session.json
            with open(ACTIVE_SESSION_FILE, 'w', encoding='utf-8') as f:
                json.dump(account, f, indent=2, ensure_ascii=False)
            
            # Mettre le mode en connexion automatiquement
            self.injection_mode_var.set("connexion")
            self.save_proxy_config()
            
            # User ID: racine ou fruitz
            user_id = account.get('user_id') or account.get('fruitz', {}).get('user_id', 'N/A')
            user_id_display = f"{user_id[:20]}..." if user_id and len(user_id) > 20 else user_id
            
            messagebox.showinfo("Succes",
                f"Compte active pour injection!\n\n"
                f"User ID: {user_id_display}\n"
                f"Email: {account.get('email', 'N/A')}\n\n"
                f"Mode: CONNEXION\n"
                f"Lancez le proxy pour vous reconnecter")
            
            self.log(f"Compte active: {account.get('email', 'N/A')}")
            
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur: {e}")
    
    def show_account_details(self):
        """Affiche les details d'un compte"""
        selection = self.account_tree.selection()
        if not selection:
            messagebox.showwarning("Attention", "Selectionnez un compte")
            return
        
        item = selection[0]
        filename = self.account_tree.item(item, 'tags')[0]
        filepath = os.path.join(CAPTURED_DIR, filename)
        
        self._show_json_dialog("Details Compte", filepath)
    
    def export_account(self):
        """Exporte un compte"""
        selection = self.account_tree.selection()
        if not selection:
            messagebox.showwarning("Attention", "Selectionnez un compte")
            return
        
        item = selection[0]
        filename = self.account_tree.item(item, 'tags')[0]
        filepath = os.path.join(CAPTURED_DIR, filename)
        
        from tkinter import filedialog
        dest = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile=filename
        )
        
        if dest:
            import shutil
            shutil.copy(filepath, dest)
            messagebox.showinfo("Succes", f"Compte exporte:\n{dest}")
    
    def _show_json_dialog(self, title: str, filepath: str):
        """Affiche un JSON dans un dialogue"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            dialog = tk.Toplevel(self)
            dialog.title(title)
            dialog.geometry("600x500")
            dialog.configure(bg=BG_SECONDARY)
            
            text = scrolledtext.ScrolledText(dialog, bg="#0a0a15", fg=SUCCESS,
                                            font=("Consolas", 9))
            text.pack(fill='both', expand=True, padx=10, pady=10)
            text.insert('1.0', json.dumps(data, indent=2, ensure_ascii=False))
            text.config(state='disabled')
            
            tk.Button(dialog, text="Fermer", command=dialog.destroy,
                     bg=BG_TERTIARY, fg=TEXT_PRIMARY).pack(pady=10)
            
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur: {e}")
    
    def on_closing(self):
        """Fermeture propre"""
        if self.proxy_running:
            if messagebox.askyesno("Quitter", "Le proxy est actif. Arreter et quitter?"):
                self.stop_proxy()
                self.destroy()
        else:
            self.destroy()


if __name__ == "__main__":
    app = AccountManager()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()