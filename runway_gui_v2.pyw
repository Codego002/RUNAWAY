"""
Runway ML Batch Processor V2 - Enhanced GUI
+ Browse Cache tab
+ Delete Account button
"""
import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import time
import os
import subprocess
import platform
import random
from pathlib import Path
from runway_ai_modifier import IMAGE_MODELS, RunwayAIModifier, model_by_label
from cache_manager import RunwayCache
import requests
import config
import json
import accounts_manager
from PIL import Image, ImageTk


# Configuration
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class RunwayGUI:
    def __init__(self):
        """Initialize GUI"""
        self.root = ctk.CTk()
        self.root.title("🎬 Runway ML Batch Processor V2")
        self.root.geometry("1000x820")
        
        # Core components
        self.cache = RunwayCache()
        self.modifier = RunwayAIModifier()
        
        # Queue and shared reference images (IMG_2, IMG_3, ... on every task)
        self.queue = []
        self.shared_refs = []
        self._cost_seq = 0
        self.processing = False
        self.paused = False
        self.current_index = 0
        
        # Use config for output directory
        self.output_dir = config.OUTPUTS_DIR
        
        # Build UI
        self.build_ui()
        
        # Load auth
        self.load_auth()
    
    def build_ui(self):
        """Build the interface"""
        
        # ============ TOP BAR ============
        top_frame = ctk.CTkFrame(self.root)
        top_frame.pack(fill="x", padx=10, pady=5)
        
        # Credits
        self.credits_label = ctk.CTkLabel(
            top_frame, 
            text="Credits: -- ⚡",
            font=("Arial", 16, "bold")
        )
        self.credits_label.pack(side="left", padx=10)
        
        # Refresh button
        ctk.CTkButton(
            top_frame,
            text="🔄",
            width=40,
            command=self.refresh_credits
        ).pack(side="left", padx=2)
        
        # Account dropdown
        ctk.CTkLabel(top_frame, text="👤", font=("Arial", 14)).pack(side="left", padx=(10, 2))
        self.account_var = ctk.StringVar(value="No accounts")
        self.account_menu = ctk.CTkOptionMenu(
            top_frame,
            variable=self.account_var,
            values=["No accounts"],
            width=200,
            command=self.on_account_changed
        )
        self.account_menu.pack(side="left", padx=2)
        
        # Launch scanner button
        ctk.CTkButton(
            top_frame,
            text="🎬 Scanner",
            width=100,
            command=self.launch_scanner_gui,
            fg_color="purple"
        ).pack(side="left", padx=5)
        
        # DELETE ACCOUNT BUTTON
        ctk.CTkButton(
            top_frame,
            text="🗑️ Delete",
            width=80,
            command=self.delete_account_dialog,
            fg_color="red",
            hover_color="darkred"
        ).pack(side="left", padx=2)
        
        # Auth status
        self.auth_label = ctk.CTkLabel(
            top_frame,
            text="Auth: ❌",
            font=("Arial", 12)
        )
        self.auth_label.pack(side="right", padx=10)
        
        # ============ NOTEBOOK/TABS ============
        self.tabview = ctk.CTkTabview(self.root)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Tab 1: Batch Processor
        self.tab_batch = self.tabview.add("📋 Batch Processor")
        self.build_batch_tab()
        
        # Tab 2: Browse Cache (NEW)
        self.tab_cache = self.tabview.add("🗂️ Browse Cache")
        self.build_cache_tab()
        
        # Set default tab
        self.tabview.set("📋 Batch Processor")
    
    def build_batch_tab(self):
        """Build batch processor tab"""
        
        # ============ QUEUE SECTION ============
        queue_label = ctk.CTkLabel(
            self.tab_batch,
            text="📋 Batch Queue",
            font=("Arial", 14, "bold")
        )
        queue_label.pack(pady=(10, 5))
        
        # Queue frame with scrollbar
        queue_container = ctk.CTkFrame(self.tab_batch)
        queue_container.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Scrollable frame
        self.queue_frame = ctk.CTkScrollableFrame(
            queue_container,
            height=200
        )
        self.queue_frame.pack(fill="both", expand=True)
        
        # ============ SETTINGS ============
        settings_frame = ctk.CTkFrame(self.tab_batch)
        settings_frame.pack(fill="x", padx=10, pady=10)
        
        # Prompt
        ctk.CTkLabel(
            settings_frame,
            text="💬 Prompt:",
            font=("Arial", 12, "bold")
        ).grid(row=0, column=0, padx=5, pady=5, sticky="w")
        
        self.prompt_entry = ctk.CTkEntry(
            settings_frame,
            placeholder_text="Enter your AI prompt here...",
            width=500
        )
        self.prompt_entry.grid(row=0, column=1, columnspan=2, padx=5, pady=5, sticky="ew")

        ctk.CTkButton(
            settings_frame,
            text="History",
            width=80,
            command=self.show_prompt_history
        ).grid(row=0, column=3, padx=5, pady=5)
        
        # Ratio
        ctk.CTkLabel(settings_frame, text="Ratio:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.ratio_var = ctk.StringVar(value="9:16")
        ratio_menu = ctk.CTkOptionMenu(
            settings_frame,
            variable=self.ratio_var,
            values=["1:1", "9:16", "16:9", "4:3", "3:4"],
            width=100,
            command=self.schedule_cost_refresh
        )
        ratio_menu.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        
        # Model
        ctk.CTkLabel(settings_frame, text="Model:").grid(row=1, column=2, padx=5, pady=5, sticky="w")
        self.model_var = ctk.StringVar(value=IMAGE_MODELS[0]["label"])
        model_menu = ctk.CTkOptionMenu(
            settings_frame,
            variable=self.model_var,
            values=[model["label"] for model in IMAGE_MODELS],
            width=200,
            command=self.schedule_cost_refresh
        )
        model_menu.grid(row=1, column=3, padx=5, pady=5, sticky="w")

        self.cost_label = ctk.CTkLabel(settings_frame, text="Coût: --", font=("Arial", 12, "bold"))
        self.cost_label.grid(row=1, column=4, padx=8, pady=5, sticky="w")

        ctk.CTkLabel(settings_frame, text="Mode:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.job_mode_var = ctk.StringVar(value="Batch")
        ctk.CTkOptionMenu(
            settings_frame,
            variable=self.job_mode_var,
            values=["Batch", "Références"],
            width=140,
            command=self.on_job_mode_changed
        ).grid(row=2, column=1, padx=5, pady=5, sticky="w")
        self.mode_hint = ctk.CTkLabel(
            settings_frame,
            text="1 tâche par image. Les réf. partagées s'ajoutent en IMG_2, IMG_3…",
            text_color="gray",
        )
        self.mode_hint.grid(row=2, column=2, columnspan=3, padx=5, pady=5, sticky="w")

        # Cache checkbox
        self.use_cache_var = ctk.BooleanVar(value=True)
        cache_check = ctk.CTkCheckBox(
            settings_frame,
            text="✓ Use cached uploads",
            variable=self.use_cache_var
        )
        cache_check.grid(row=3, column=0, columnspan=2, padx=5, pady=5, sticky="w")

        # Auto-download checkbox
        self.auto_download_var = ctk.BooleanVar(value=True)
        download_check = ctk.CTkCheckBox(
            settings_frame,
            text="✓ Auto-download results",
            variable=self.auto_download_var
        )
        download_check.grid(row=3, column=2, columnspan=2, padx=5, pady=5, sticky="w")

        self.refs_label = ctk.CTkLabel(settings_frame, text="Réf. partagées: aucune", anchor="w")
        self.refs_label.grid(row=4, column=0, columnspan=2, padx=5, pady=5, sticky="w")
        ctk.CTkButton(
            settings_frame,
            text="Ajouter réf.",
            width=110,
            command=self.add_shared_refs
        ).grid(row=4, column=2, padx=5, pady=5, sticky="w")
        ctk.CTkButton(
            settings_frame,
            text="Vider réf.",
            width=100,
            command=self.clear_shared_refs
        ).grid(row=4, column=3, padx=5, pady=5, sticky="w")
        
        settings_frame.columnconfigure(1, weight=1)
        
        # ============ ACTIONS ============
        actions_frame = ctk.CTkFrame(self.tab_batch)
        actions_frame.pack(fill="x", padx=10, pady=10)
        
        # Add images
        ctk.CTkButton(
            actions_frame,
            text="📤 Add Images",
            command=self.add_images,
            width=120,
            height=35
        ).pack(side="left", padx=5)
        
        # Add from cache (NEW)
        ctk.CTkButton(
            actions_frame,
            text="💾 Add from Cache",
            command=self.add_from_cache,
            width=140,
            height=35,
            fg_color="orange"
        ).pack(side="left", padx=5)
        
        # Start
        self.start_btn = ctk.CTkButton(
            actions_frame,
            text="▶️  Start Batch",
            command=self.start_batch,
            width=120,
            height=35,
            fg_color="green"
        )
        self.start_btn.pack(side="left", padx=5)
        
        # Pause
        self.pause_btn = ctk.CTkButton(
            actions_frame,
            text="⏸️  Pause",
            command=self.toggle_pause,
            width=100,
            height=35,
            state="disabled"
        )
        self.pause_btn.pack(side="left", padx=5)
        
        # Stop
        self.stop_btn = ctk.CTkButton(
            actions_frame,
            text="⏹️  Stop",
            command=self.stop_batch,
            width=100,
            height=35,
            state="disabled",
            fg_color="red"
        )
        self.stop_btn.pack(side="left", padx=5)
        
        # Retry Failed
        self.retry_btn = ctk.CTkButton(
            actions_frame,
            text="🔄 Retry Failed",
            command=self.retry_failed,
            width=120,
            height=35,
            fg_color="purple"
        )
        self.retry_btn.pack(side="left", padx=5)
        
        # Clear
        ctk.CTkButton(
            actions_frame,
            text="🗑️  Clear",
            command=self.clear_queue,
            width=100,
            height=35
        ).pack(side="left", padx=5)
        
        # Open outputs
        ctk.CTkButton(
            actions_frame,
            text="📁 Open Outputs",
            command=self.open_outputs,
            width=120,
            height=35
        ).pack(side="right", padx=5)
        
        # ============ PROGRESS ============
        progress_frame = ctk.CTkFrame(self.tab_batch)
        progress_frame.pack(fill="x", padx=10, pady=5)
        
        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(progress_frame)
        self.progress_bar.pack(fill="x", padx=10, pady=5)
        self.progress_bar.set(0)
        
        # Progress label
        self.progress_label = ctk.CTkLabel(
            progress_frame,
            text="Ready",
            font=("Arial", 12)
        )
        self.progress_label.pack(pady=5)
    
    def build_cache_tab(self):
        """Build cache browser tab (NEW)"""
        
        # Top controls
        top_controls = ctk.CTkFrame(self.tab_cache)
        top_controls.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            top_controls,
            text="🗂️ Cached Uploads",
            font=("Arial", 16, "bold")
        ).pack(side="left", padx=10)
        
        ctk.CTkButton(
            top_controls,
            text="🔄 Refresh",
            command=self.refresh_cache_list,
            width=100
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            top_controls,
            text="🗑️ Clear All Cache",
            command=self.clear_all_cache,
            fg_color="red",
            width=140
        ).pack(side="right", padx=5)
        
        # Cache list
        cache_container = ctk.CTkScrollableFrame(self.tab_cache)
        cache_container.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.cache_list_frame = cache_container
        
        # Load cache
        self.refresh_cache_list()
    
    def refresh_cache_list(self):
        """Refresh cache list display"""
        # Clear existing
        for widget in self.cache_list_frame.winfo_children():
            widget.destroy()
        
        # Get cached items
        cached = self.cache.list_cached_uploads()
        
        if not cached:
            ctk.CTkLabel(
                self.cache_list_frame,
                text="No cached uploads yet. Upload some images first!",
                font=("Arial", 12),
                text_color="gray"
            ).pack(pady=20)
            return
        
        # Display each cached item
        for idx, item in enumerate(cached):
            self.add_cache_item_widget(item, idx)
    
    def add_cache_item_widget(self, item, idx):
        """Add a cache item widget"""
        item_frame = ctk.CTkFrame(self.cache_list_frame)
        item_frame.pack(fill="x", padx=5, pady=5)
        
        # Thumbnail (if available)
        try:
            img = Image.open(item['file_path'])
            img.thumbnail((80, 80))
            photo = ctk.CTkImage(light_image=img, dark_image=img, size=(80, 80))
            
            img_label = ctk.CTkLabel(item_frame, text="", image=photo)
            img_label.image = photo  # Keep reference
            img_label.pack(side="left", padx=10)
        except:
            # No thumbnail
            ctk.CTkLabel(
                item_frame,
                text="📷",
                font=("Arial", 40)
            ).pack(side="left", padx=10)
        
        # Info
        info_frame = ctk.CTkFrame(item_frame)
        info_frame.pack(side="left", fill="both", expand=True, padx=10)
        
        ctk.CTkLabel(
            info_frame,
            text=os.path.basename(item['file_path']),
            font=("Arial", 12, "bold"),
            anchor="w"
        ).pack(anchor="w")
        
        ctk.CTkLabel(
            info_frame,
            text=f"Asset ID: {item['asset_id'][:20]}...",
            font=("Arial", 10),
            text_color="gray",
            anchor="w"
        ).pack(anchor="w")
        
        ctk.CTkLabel(
            info_frame,
            text=f"Uploaded: {item['uploaded_at']}",
            font=("Arial", 9),
            text_color="gray",
            anchor="w"
        ).pack(anchor="w")
        
        # Actions
        btn_frame = ctk.CTkFrame(item_frame)
        btn_frame.pack(side="right", padx=10)
        
        ctk.CTkButton(
            btn_frame,
            text="➕ Add to Queue",
            command=lambda: self.add_cache_to_queue(item),
            width=120,
            height=30,
            fg_color="green"
        ).pack(pady=2)
        
        ctk.CTkButton(
            btn_frame,
            text="🗑️ Remove",
            command=lambda: self.remove_from_cache(item),
            width=120,
            height=30,
            fg_color="red"
        ).pack(pady=2)
    
    def add_cache_to_queue(self, item):
        """Add cached item to batch queue"""
        # Use cached asset_id
        self.queue.append({
            'file': item['file_path'],
            'asset_id': item['asset_id'],
            'asset_url': item.get('asset_url'),
            'from_cache': True
        })
        self.update_queue_display()
        self.update_refs_label()
        self.schedule_cost_refresh()
        messagebox.showinfo("Added", f"Added {os.path.basename(item['file_path'])} to queue from cache!")
    
    def remove_from_cache(self, item):
        """Remove item from cache"""
        if messagebox.askyesno("Confirm", "Remove this item from cache?"):
            # Remove from database
            self.cache.remove_upload(item['file_hash'])
            self.refresh_cache_list()
            messagebox.showinfo("Removed", "Item removed from cache")
    
    def clear_all_cache(self):
        """Clear all cache"""
        if messagebox.askyesno("Confirm", "Clear ALL cached uploads? This cannot be undone!"):
            self.cache.clear_all()
            self.refresh_cache_list()
            messagebox.showinfo("Cleared", "All cache cleared!")
    
    def delete_account_dialog(self):
        """Show delete account dialog (DANGEROUS!)"""
        # Warning dialog
        response = messagebox.askquestion(
            "⚠️ DELETE ACCOUNT",
            "⚠️ DANGER! This will PERMANENTLY DELETE your Runway ML account!\n\n"
            "This action CANNOT be undone!\n\n"
            "Are you absolutely sure you want to continue?",
            icon="warning"
        )
        
        if response != "yes":
            return
        
        # Password dialog
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("⚠️ Confirm Delete Account")
        dialog.geometry("400x250")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ctk.CTkLabel(
            dialog,
            text="⚠️ DELETE ACCOUNT",
            font=("Arial", 18, "bold"),
            text_color="red"
        ).pack(pady=20)
        
        ctk.CTkLabel(
            dialog,
            text="Enter your Runway ML password to confirm:",
            font=("Arial", 12)
        ).pack(pady=10)
        
        password_entry = ctk.CTkEntry(
            dialog,
            placeholder_text="Password",
            show="*",
            width=300
        )
        password_entry.pack(pady=10)
        
        def execute_delete():
            password = password_entry.get()
            if not password:
                messagebox.showerror("Error", "Password required!")
                return
            
            # Confirm again
            final_confirm = messagebox.askquestion(
                "FINAL WARNING",
                f"LAST CHANCE! Delete account with password?\n\n"
                f"This will PERMANENTLY delete your account!\n\n"
                f"Type YES to confirm:",
                icon="warning"
            )
            
            if final_confirm != "yes":
                dialog.destroy()
                return
            
            # Execute delete
            try:
                self.delete_account(password)
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete account: {e}")
        
        ctk.CTkButton(
            dialog,
            text="🗑️ DELETE ACCOUNT",
            command=execute_delete,
            fg_color="red",
            hover_color="darkred",
            width=200,
            height=40
        ).pack(pady=20)
        
        ctk.CTkButton(
            dialog,
            text="Cancel",
            command=dialog.destroy,
            width=200
        ).pack()
    
    def delete_account(self, password):
        """Execute account deletion"""
        # Use the already-loaded modifier session (no need to re-read auth file)
        if not self.modifier.bearer_token:
            raise Exception("No auth loaded! Select an account first.")
        
        # Make DELETE request using modifier's session (handles encoding properly)
        url = f"{self.modifier.base_url}/v1/profile"
        body = {"password": password}
        
        response = self.modifier.session.delete(url, json=body)
        
        # Force UTF-8 response decoding to avoid charmap errors
        response.encoding = 'utf-8'
        
        if response.status_code == 200:
            if self.modifier.team_id:
                accounts_manager.remove_account(str(self.modifier.team_id))
            messagebox.showinfo("Success", "Account deleted successfully!")
            self.refresh_accounts_dropdown()
            # Charger le prochain compte disponible
            next_account = accounts_manager.get_active_account()
            if next_account:
                self.modifier.load_account_data(next_account)
                self.auth_label.configure(text="Auth: OK", text_color="green")
                threading.Thread(target=self.refresh_credits, daemon=True).start()
            else:
                self.auth_label.configure(text="Auth: No accounts", text_color="red")
                self.credits_label.configure(text="Credits: --")
        else:
            try:
                err_text = response.text
            except Exception:
                err_text = f"HTTP {response.status_code}"
            raise Exception(f"Delete failed: {response.status_code} - {err_text}")
    
    def save_prompt_history(self, prompt: str):
        """Sauvegarde un prompt dans l'historique (max 50 entrees)"""
        prompt = prompt.strip()
        if not prompt:
            return
        try:
            history = []
            if config.PROMPT_HISTORY.exists():
                with open(config.PROMPT_HISTORY, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            if prompt in history:
                history.remove(prompt)
            history.insert(0, prompt)
            history = history[:50]
            with open(config.PROMPT_HISTORY, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def show_prompt_history(self):
        """Affiche la fenetre d'historique des prompts"""
        try:
            history = []
            if config.PROMPT_HISTORY.exists():
                with open(config.PROMPT_HISTORY, 'r', encoding='utf-8') as f:
                    history = json.load(f)
        except Exception:
            history = []

        if not history:
            messagebox.showinfo("History", "No prompt history yet.")
            return

        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Prompt History")
        dialog.geometry("600x400")
        dialog.transient(self.root)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Select a prompt to reuse:", font=("Arial", 12, "bold")).pack(pady=10)

        frame = ctk.CTkScrollableFrame(dialog)
        frame.pack(fill="both", expand=True, padx=10, pady=5)

        def select_prompt(p):
            self.prompt_entry.delete(0, "end")
            self.prompt_entry.insert(0, p)
            dialog.destroy()

        for p in history:
            row = ctk.CTkFrame(frame)
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=p, wraplength=480, anchor="w", justify="left").pack(side="left", padx=8, fill="x", expand=True)
            ctk.CTkButton(row, text="Use", width=60, command=lambda x=p: select_prompt(x)).pack(side="right", padx=5)

    def add_from_cache(self):
        """Add multiple items from cache to queue"""
        # Show cache selection dialog
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Select from Cache")
        dialog.geometry("600x500")
        dialog.transient(self.root)
        
        ctk.CTkLabel(
            dialog,
            text="Select items to add to queue:",
            font=("Arial", 14, "bold")
        ).pack(pady=10)
        
        # Scrollable list
        list_frame = ctk.CTkScrollableFrame(dialog, height=350)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        cached = self.cache.list_cached_uploads()
        selected_vars = []
        
        for item in cached:
            var = ctk.BooleanVar(value=False)
            selected_vars.append((var, item))
            
            frame = ctk.CTkFrame(list_frame)
            frame.pack(fill="x", pady=2)
            
            ctk.CTkCheckBox(
                frame,
                text=os.path.basename(item['file_path']),
                variable=var
            ).pack(side="left", padx=10)
        
        def add_selected():
            count = 0
            for var, item in selected_vars:
                if var.get():
                    self.add_cache_to_queue(item)
                    count += 1
            dialog.destroy()
            messagebox.showinfo("Added", f"Added {count} items from cache!")
        
        ctk.CTkButton(
            dialog,
            text="Add Selected",
            command=add_selected,
            width=150,
            height=35,
            fg_color="green"
        ).pack(pady=10)
    
    # ========== EXISTING METHODS (keep from original) ==========
    
    def load_auth(self):
        """Load auth - try accounts.json first, fallback to old auth file"""
        # Always refresh from the latest captured auth file when available
        if config.AUTH_FILE.exists():
            accounts_manager.import_from_old_auth_file(str(config.AUTH_FILE))
        
        # Load accounts into dropdown
        self.refresh_accounts_dropdown()
        
        # Load active account
        account = accounts_manager.get_active_account()
        if account:
            success = self.modifier.load_account_data(account)
            if success:
                label = account.get("label", f"Account {account.get('team_id')}")
                self.auth_label.configure(text="Auth: ✅", text_color="green")
                self.refresh_credits()
                self.schedule_cost_refresh()
                return
        
        # Fallback: try old auth file directly
        if config.AUTH_FILE.exists():
            success = self.modifier.load_from_captured(str(config.AUTH_FILE))
            if success:
                self.auth_label.configure(text="Auth: ✅", text_color="green")
                self.refresh_credits()
                self.schedule_cost_refresh()
                return
        
        self.auth_label.configure(text="Auth: ❌ No accounts", text_color="red")
        self.schedule_cost_refresh()
    
    def refresh_accounts_dropdown(self):
        """Refresh the accounts dropdown with current accounts"""
        accs = accounts_manager.list_accounts()
        data = accounts_manager.load_accounts()
        active_id = data.get("active_account")
        
        if not accs:
            self.account_menu.configure(values=["No accounts"])
            self.account_var.set("No accounts")
            return
        
        # Build labels list
        labels = [f"{a.get('label', 'Unknown')} [{a['team_id']}]" for a in accs]
        self.account_menu.configure(values=labels)
        
        # Select active account
        for i, acc in enumerate(accs):
            if str(acc['team_id']) == str(active_id):
                self.account_var.set(labels[i])
                return
        
        # Default to first
        self.account_var.set(labels[0])
    
    def on_account_changed(self, selection: str):
        """Called when user selects a different account"""
        # Extract team_id from selection "[12345]"
        import re
        match = re.search(r'\[(\d+)\]', selection)
        if not match:
            return
        
        team_id = match.group(1)
        
        # Set active account
        accounts_manager.set_active_account(team_id)
        
        # Load it into modifier
        account = accounts_manager.get_account(team_id)
        if account:
            success = self.modifier.load_account_data(account)
            if success:
                self.auth_label.configure(text="Auth: ✅", text_color="green")
                # Refresh credits in background
                threading.Thread(target=self.refresh_credits, daemon=True).start()
                self.schedule_cost_refresh()
                print(f"🔄 Switched to account: {account.get('label')}")
            else:
                self.auth_label.configure(text="Auth: ❌ Failed", text_color="red")
    
    def refresh_credits(self):
        """Refresh credits display (Runway accurate balance)"""
        try:
            credits = None
            # 1. Recuperer le team_id depuis le profile
            profile_resp = self.modifier.session.get(
                f"{self.modifier.base_url}/v1/profile"
            )
            if profile_resp.status_code == 401:
                # Token expiré - supprimer ce compte
                active = accounts_manager.get_active_account()
                if active:
                    accounts_manager.remove_account(str(active["team_id"]))
                    print(f"Compte supprime (401): {active.get('label')}")
                self.root.after(0, self.refresh_accounts_dropdown)
                next_account = accounts_manager.get_active_account()
                if next_account:
                    self.modifier.load_account_data(next_account)
                    self.root.after(0, lambda: self.auth_label.configure(text="Auth: OK", text_color="green"))
                    threading.Thread(target=self.refresh_credits, daemon=True).start()
                else:
                    self.root.after(0, lambda: self.auth_label.configure(text="Auth: No accounts", text_color="red"))
                    self.root.after(0, lambda: self.credits_label.configure(text="Credits: --"))
                return
            if profile_resp.status_code != 200:
                raise Exception("Profile fetch failed")
            profile_data = profile_resp.json()
            user = profile_data.get("user", {})
            team_id = user.get("id")
            if not team_id:
                raise Exception("Team ID introuvable")

            # Mettre a jour nom/email dans accounts.json et le dropdown
            first = user.get("firstName", "")
            last  = user.get("lastName", "")
            email = user.get("email", "")
            account = accounts_manager.get_account(str(team_id))
            if account:
                account["first_name"] = first
                account["last_name"]  = last
                account["email"]      = email
                if first or last:
                    account["label"] = f"{first} {last}".strip() + f" ({email})"
                elif email:
                    account["label"] = email
                data = accounts_manager.load_accounts()
                data["accounts"][str(team_id)] = account
                accounts_manager.save_accounts(data)
                self.root.after(0, self.refresh_accounts_dropdown)

            # The app total is monthly remaining + purchased.
            # Monthly: profile/features permitted.numPlanCredits - used.numPlanCredits
            # Purchased: profile user.gpuCredits (the number never appears as one field)
            purchased = user.get("gpuCredits") or 0
            features_resp = self.modifier.session.get(
                f"{self.modifier.base_url}/v1/profile/features",
                params={"asTeamId": team_id}
            )
            if features_resp.status_code == 200:
                features = features_resp.json().get("features", {})
                permitted = features.get("permitted", {}).get("numPlanCredits")
                used      = features.get("used", {}).get("numPlanCredits", 0)
                if permitted is not None:
                    credits = (permitted - used) + purchased

            # Fallback: last plan balance from the usage ledger, plus purchased credits
            if credits is None:
                usage_resp = self.modifier.session.get(
                    f"{self.modifier.base_url}/v1/billing/credits_usages",
                    params={"asTeamId": team_id}
                )
                if usage_resp.status_code == 200:
                    usages = usage_resp.json().get("creditUsages", [])
                    if usages:
                        credits = int(usages[0].get("newBalance") or 0) + purchased

            if credits is None:
                credits = purchased

            print(f"Credits: {credits} | Team: {team_id}")
            self.cache.save_profile(team_id, credits)
            self.credits_label.configure(text=f"Credits: {credits}")
        except Exception as e:
            print(f"Error refreshing credits: {e}")
            self.credits_label.configure(text="Credits: --")
    
    def launch_scanner_gui(self):
        """Launch scanner GUI"""
        try:
            if platform.system() == "Windows":
                subprocess.Popen(["python", "runway_scanner_gui.py"], 
                               creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                subprocess.Popen(["python3", "runway_scanner_gui.py"])
            messagebox.showinfo("Launched", "Scanner GUI launched in background!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch scanner: {e}")
    
    def add_images(self):
        """Add images to queue"""
        files = filedialog.askopenfilenames(
            title="Select images",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.webp *.heic")]
        )
        
        for file in files:
            # Check if already in queue
            already_added = any(item['file'] == file for item in self.queue)
            if already_added:
                continue
            
            self.queue.append({
                'file': file,
                'from_cache': False,
                'status': 'waiting',  # waiting, processing, success, failed
                'error': None,
                'result_urls': None,
                'retries': 0
            })
        
        self.update_queue_display()
        self.update_refs_label()
        self.schedule_cost_refresh()
    
    def update_queue_display(self):
        """Update queue display with status colors"""
        # Clear
        for widget in self.queue_frame.winfo_children():
            widget.destroy()
        
        # Add items
        for idx, item in enumerate(self.queue):
            frame = ctk.CTkFrame(self.queue_frame)
            frame.pack(fill="x", pady=2)
            
            # Status icon with color
            status = item.get('status', 'waiting')
            if status == 'waiting':
                icon = "⏳"
                color = "gray"
            elif status == 'processing':
                icon = "🔄"
                color = "yellow"
            elif status == 'success':
                icon = "✅"
                color = "green"
            elif status == 'failed':
                icon = "❌"
                color = "red"
            else:
                icon = str(idx + 1)
                color = "gray"
            
            ctk.CTkLabel(
                frame,
                text=icon,
                width=30,
                text_color=color
            ).pack(side="left", padx=5)
            
            # Filename. In Références mode the row order is the IMG tag order.
            filename = os.path.basename(item['file'])
            if self.job_mode_var.get() == "Références":
                tag = f"IMG_{idx + 1}  "
            elif self.shared_refs:
                tag = "IMG_1  "
            else:
                tag = ""
            cache_tag = " [CACHED]" if item.get('from_cache') else ""
            error_tag = f" - {item.get('error', '')}" if item.get('error') else ""
            
            ctk.CTkLabel(
                frame, 
                text=f"{tag}{filename}{cache_tag}{error_tag}",
                anchor="w"
            ).pack(side="left", fill="x", expand=True, padx=5)
            
            # Remove button
            ctk.CTkButton(
                frame,
                text="✕",
                width=30,
                command=lambda i=idx: self.remove_from_queue(i)
            ).pack(side="right", padx=5)
    
    def remove_from_queue(self, index):
        """Remove item from queue"""
        if not self.processing or index >= self.current_index:
            self.queue.pop(index)
            self.update_queue_display()
            self.update_refs_label()
            self.schedule_cost_refresh()
    
    def clear_queue(self):
        """Clear queue"""
        if not self.processing:
            self.queue = []
            self.current_index = 0
            self.update_queue_display()
            self.update_refs_label()
            self.schedule_cost_refresh()
    
    def next_batch_output_dir(self):
        """Next unused folder: outputs/AA_MM_JJ_A (then B..Z, then AA)."""
        config.OUTPUTS_DIR.mkdir(exist_ok=True)
        prefix = time.strftime("%y_%m_%d")
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        for ch in letters:
            candidate = config.OUTPUTS_DIR / f"{prefix}_{ch}"
            if not candidate.exists():
                return candidate
        for ch1 in letters:
            for ch2 in letters:
                candidate = config.OUTPUTS_DIR / f"{prefix}_{ch1}{ch2}"
                if not candidate.exists():
                    return candidate
        raise RuntimeError("Too many batches today")

    def prepare_batch_output(self, prompt: str):
        """Create dated batch folder and write prompt.txt."""
        batch_dir = self.next_batch_output_dir()
        batch_dir.mkdir(parents=True, exist_ok=False)
        (batch_dir / "prompt.txt").write_text(prompt.strip() + "\n", encoding="utf-8")
        self.output_dir = batch_dir
        print(f"Batch folder: {batch_dir}")
        return batch_dir

    def start_batch(self):
        """Start batch processing"""
        if not self.queue:
            messagebox.showwarning("Empty Queue", "Add some images first!")
            return
        
        if not self.prompt_entry.get():
            messagebox.showwarning("No Prompt", "Enter a prompt first!")
            return

        token_problem = self.modifier.uploader.token_error()
        if token_problem:
            messagebox.showerror("Auth", token_problem)
            return

        model = model_by_label(self.model_var.get())
        grouped = self.job_mode_var.get() == "Références"
        ref_count = (len(self.queue) + len(self.shared_refs)) if grouped else (1 + len(self.shared_refs))
        if grouped and ref_count < 2:
            messagebox.showwarning(
                "Références",
                "Le mode Références envoie toutes les images dans une seule tâche.\nAjoute au moins 2 images."
            )
            return
        if model.get("single_ref") and ref_count > 1:
            if not messagebox.askyesno(
                model["label"],
                f"{model['label']} n'accepte qu'une seule image de référence.\n"
                "Seule IMG_1 sera envoyée. Continuer ?"
            ):
                return
        
        # Reset index for new batch
        self.current_index = 0
        
        self.processing = True
        self.paused = False
        self.start_btn.configure(state="disabled")
        self.pause_btn.configure(state="normal")
        self.stop_btn.configure(state="normal")
        
        threading.Thread(target=self.process_batch, daemon=True).start()

    def on_job_mode_changed(self, _value=None):
        if self.job_mode_var.get() == "Références":
            self.mode_hint.configure(text="Une seule tâche : la file devient IMG_1, IMG_2, IMG_3…")
        else:
            self.mode_hint.configure(text="1 tâche par image. Les réf. partagées s'ajoutent en IMG_2, IMG_3…")
        self.update_queue_display()
        self.schedule_cost_refresh()

    def add_shared_refs(self):
        """Extra images appended to every task as IMG_2, IMG_3, ..."""
        files = filedialog.askopenfilenames(
            title="Images de référence",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.webp *.heic")]
        )
        for file in files:
            if any(ref["file"] == file for ref in self.shared_refs):
                continue
            self.shared_refs.append({"file": file, "from_cache": False})
        self.update_queue_display()
        self.schedule_cost_refresh()

    def clear_shared_refs(self):
        self.shared_refs = []
        self.update_queue_display()
        self.schedule_cost_refresh()

    def update_refs_label(self):
        count = len(self.shared_refs)
        if count == 0:
            text = "Réf. partagées: aucune"
        else:
            start = len(self.queue) + 1 if self.job_mode_var.get() == "Références" else 2
            tags = ", ".join(f"IMG_{start + i}" for i in range(count))
            names = ", ".join(os.path.basename(ref["file"]) for ref in self.shared_refs)
            text = f"Réf. partagées: {tags} — {names}"
        if model_by_label(self.model_var.get()).get("single_ref"):
            text += "  · ce modèle n'envoie que IMG_1"
        self.refs_label.configure(text=text)

    def schedule_cost_refresh(self, *_args):
        self._cost_seq += 1
        seq = self._cost_seq
        self.cost_label.configure(text="Coût: …")
        self.update_refs_label()
        threading.Thread(target=self._fetch_cost, args=(seq,), daemon=True).start()

    def _fetch_cost(self, seq):
        model = model_by_label(self.model_var.get())
        grouped = self.job_mode_var.get() == "Références"
        cost = None
        offline = not bool(self.modifier.bearer_token)
        if not offline:
            try:
                estimate = self.modifier.estimate_feature_cost(model["id"], self.ratio_var.get(), 1)
                cost = estimate.get("cost")
            except Exception as exc:
                print(f"Cost estimate failed: {exc}")
                offline = True
        if cost is None:
            cost = model["credits"]
            offline = True
        if grouped:
            text = f"Coût: {cost} cr (1 tâche)"
        elif len(self.queue) > 1:
            text = f"Coût: {cost} cr × {len(self.queue)} = {cost * len(self.queue)} cr"
        else:
            text = f"Coût: {cost} cr / image"
        if offline:
            text = "≈ " + text

        def apply():
            if seq == self._cost_seq:
                self.cost_label.configure(text=text)

        self.root.after(0, apply)

    def _asset_for(self, item):
        """Cached asset, or upload. Returns {assetId, url}."""
        if item.get("asset_id") and item.get("asset_url"):
            return {"assetId": item["asset_id"], "url": item["asset_url"]}
        if self.use_cache_var.get():
            cached = self.cache.check_cached_upload(item["file"])
            if cached:
                return cached
        return self.upload_and_cache(item["file"])

    def process_batch(self):
        """Process batch with intelligent error handling.

        Batch: one task per queue image, shared refs appended.
        Références: one task, every queue image is IMG_1, IMG_2, ...
        """
        grouped = self.job_mode_var.get() == "Références"
        jobs = [list(self.queue)] if grouped else [[item] for item in self.queue]
        total = len(jobs)
        success_count = 0
        failed_count = 0

        self.prepare_batch_output(self.prompt_entry.get())
        error_log_path = self.output_dir / f"errors_{time.strftime('%Y%m%d_%H%M%S')}.log"

        try:
            shared_assets = [self._asset_for(ref) for ref in self.shared_refs]
        except Exception as exc:
            error_str = str(exc)
            for item in self.queue:
                item["status"] = "failed"
                item["error"] = error_str[:160]
            with open(error_log_path, "a", encoding="utf-8") as handle:
                handle.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] shared refs\n  Error: {error_str}\n\n")
            self.root.after(0, self.update_queue_display)
            self._finish_batch(0, len(jobs), error_log_path)
            return

        for idx, group in enumerate(jobs):
            if not self.processing:
                break
            while self.paused and self.processing:
                time.sleep(0.1)
            if not self.processing:
                break

            self.current_index = idx
            filename = ", ".join(os.path.basename(item["file"]) for item in group)
            self.progress_bar.set((idx + 1) / total)
            self.progress_label.configure(text=f"Processing {idx + 1}/{total}: {filename}")
            for item in group:
                item["status"] = "processing"
            self.root.after(0, self.update_queue_display)

            try:
                assets = [self._asset_for(item) for item in group]
                reference_images = [
                    {"assetId": asset["assetId"], "url": asset.get("url")}
                    for asset in assets + shared_assets
                ]
                model = model_by_label(self.model_var.get())
                seed = random.randint(1, 2**32 - 1) if model["family"] == "gen4" else None
                ai_task = self.modifier.create_ai_task(
                    prompt=self.prompt_entry.get(),
                    reference_images=reference_images,
                    aspect_ratio=self.ratio_var.get(),
                    num_images=1,
                    task_type=model["id"],
                    seed=seed,
                )
                if not ai_task:
                    raise Exception("Failed to create AI task")
                self.save_prompt_history(self.prompt_entry.get())

                completed_task = self.modifier.wait_for_completion(ai_task["id"], max_wait=300)
                if not completed_task:
                    raise Exception("Task failed or timeout")
                if completed_task.get("status") == "FAILED":
                    error_info = completed_task.get("failure", {})
                    error_reason = error_info.get("reason", "Unknown")
                    error_msg = error_info.get("errorMessage", "No details")
                    raise Exception(f"{error_reason}: {error_msg}")

                result_urls = self.modifier.get_result_urls(completed_task)
                if not result_urls:
                    raise Exception("No results generated")
                if self.auto_download_var.get():
                    self.download_results(group[0]["file"], result_urls)

                for item in group:
                    item["status"] = "success"
                    item["result_urls"] = result_urls
                success_count += 1
                print(f"✅ SUCCESS: {filename}")
            except Exception as exc:
                error_str = str(exc)
                for item in group:
                    item["status"] = "failed"
                    item["error"] = error_str[:160]
                failed_count += 1
                with open(error_log_path, "a", encoding="utf-8") as handle:
                    handle.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {filename}\n")
                    handle.write(f"  Error: {error_str}\n\n")
                print(f"❌ FAILED: {filename} - {error_str}")

            self.root.after(0, self.update_queue_display)

        self._finish_batch(success_count, failed_count, error_log_path)

    def _finish_batch(self, success_count, failed_count, error_log_path):
        
        # BATCH COMPLETE - show summary
        self.processing = False
        self.start_btn.configure(state="normal")
        self.pause_btn.configure(state="disabled")
        self.stop_btn.configure(state="disabled")
        
        # Final summary
        summary = f"Batch Complete!\n\n"
        summary += f"✅ Success: {success_count}\n"
        summary += f"❌ Failed: {failed_count}\n"
        summary += f"\nFolder: {self.output_dir.name}"
        
        if failed_count > 0:
            summary += f"\nError log saved to:\n{error_log_path.name}"
        
        self.progress_label.configure(text=f"Complete! ✅{success_count} ❌{failed_count}")
        
        # Auto-refresh credits after batch
        self.refresh_credits()
        
        messagebox.showinfo("Batch Complete", summary)
    
    def upload_and_cache(self, image_path):
        """Upload image and cache it"""
        asset = self.modifier.upload_image_for_ai(image_path)
        
        if not asset:
            detail = getattr(self.modifier.uploader, "last_error", None) or "Upload failed"
            raise Exception(detail)
        
        # Cache it
        self.cache.save_upload(
            image_path,
            asset['assetId'],
            asset['url']
        )
        
        return asset
    
    def download_results(self, original_path, urls):
        """Download result images with retry and no overwrite"""
        for i, url in enumerate(urls, 1):
            try:
                # Generate unique filename (no overwrite)
                base_name = Path(original_path).stem
                output_path = self.output_dir / f"{base_name}_result_{i}.png"
                
                # Check if file exists and find unique name
                counter = 1
                while output_path.exists():
                    output_path = self.output_dir / f"{base_name}_result_{i}_{counter}.png"
                    counter += 1
                
                # Download with retry (use modifier.session for proxy support)
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        response = self.modifier.session.get(url, stream=True, timeout=60)
                        response.raise_for_status()
                        
                        with open(output_path, 'wb') as f:
                            for chunk in response.iter_content(8192):
                                f.write(chunk)
                        
                        print(f"✅ Downloaded: {output_path.name}")
                        break
                    except Exception as e:
                        if attempt < max_retries - 1:
                            print(f"⚠️ Retry {attempt + 1}/{max_retries}...")
                            time.sleep(2)
                        else:
                            raise
            
            except Exception as e:
                print(f"❌ Download failed: {e}")
                # Continue with next URL instead of stopping
                continue
    
    def toggle_pause(self):
        """Toggle pause"""
        self.paused = not self.paused
        if self.paused:
            self.pause_btn.configure(text="▶️  Resume")
            self.progress_label.configure(text="Paused")
        else:
            self.pause_btn.configure(text="⏸️  Pause")
    
    def stop_batch(self):
        """Stop batch"""
        self.processing = False
        self.paused = False
        self.start_btn.configure(state="normal")
        self.pause_btn.configure(state="disabled")
        self.stop_btn.configure(state="disabled")
        self.progress_label.configure(text="Stopped")
    
    def retry_failed(self):
        """Retry only failed images"""
        if self.processing:
            messagebox.showwarning("Processing", "Stop current batch first!")
            return
        
        # Count failed items
        failed_items = [item for item in self.queue if item.get('status') == 'failed']
        
        if not failed_items:
            messagebox.showinfo("No Failures", "No failed images to retry!")
            return
        
        # Ask confirmation
        count = len(failed_items)
        if not messagebox.askyesno("Retry Failed", f"Retry {count} failed image(s)?"):
            return
        
        # Reset failed items to waiting
        for item in failed_items:
            item['status'] = 'waiting'
            item['error'] = None
            item['retries'] += 1
        
        # Update display
        self.update_queue_display()
        
        # Filter queue to only failed items
        original_queue = self.queue.copy()
        self.queue = failed_items
        self.current_index = 0
        
        # Start processing
        self.processing = True
        self.paused = False
        self.start_btn.configure(state="disabled")
        self.pause_btn.configure(state="normal")
        self.stop_btn.configure(state="normal")
        
        def restore_and_process():
            self.process_batch()
            # Restore original queue after retry
            self.queue = original_queue
            self.update_queue_display()
        
        threading.Thread(target=restore_and_process, daemon=True).start()
    
    def open_outputs(self):
        """Open outputs folder"""
        if platform.system() == "Windows":
            os.startfile(self.output_dir)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", self.output_dir])
        else:
            subprocess.Popen(["xdg-open", self.output_dir])
    
    def run(self):
        """Run the application"""
        self.root.mainloop()


if __name__ == "__main__":
    app = RunwayGUI()
    app.run()
