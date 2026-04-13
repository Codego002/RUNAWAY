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
from runway_ai_modifier import RunwayAIModifier
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
        self.root.geometry("1000x750")
        
        # Core components
        self.cache = RunwayCache()
        self.modifier = RunwayAIModifier()
        
        # Queue
        self.queue = []
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
        self.prompt_entry.grid(row=0, column=1, columnspan=3, padx=5, pady=5, sticky="ew")
        
        # Ratio
        ctk.CTkLabel(settings_frame, text="Ratio:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.ratio_var = ctk.StringVar(value="9:16")
        ratio_menu = ctk.CTkOptionMenu(
            settings_frame,
            variable=self.ratio_var,
            values=["1:1", "9:16", "16:9", "4:3", "3:4"],
            width=100
        )
        ratio_menu.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        
        # Model
        ctk.CTkLabel(settings_frame, text="Model:").grid(row=1, column=2, padx=5, pady=5, sticky="w")
        self.model_var = ctk.StringVar(value="gemini_image")
        model_menu = ctk.CTkOptionMenu(
            settings_frame,
            variable=self.model_var,
            values=["gemini_image", "ref_image_to_image", "ref_image_to_image_turbo"],
            width=200
        )
        model_menu.grid(row=1, column=3, padx=5, pady=5, sticky="w")
        
        # Cache checkbox
        self.use_cache_var = ctk.BooleanVar(value=True)
        cache_check = ctk.CTkCheckBox(
            settings_frame,
            text="✓ Use cached uploads",
            variable=self.use_cache_var
        )
        cache_check.grid(row=2, column=0, padx=5, pady=5, sticky="w")
        
        # Auto-download checkbox
        self.auto_download_var = ctk.BooleanVar(value=True)
        download_check = ctk.CTkCheckBox(
            settings_frame,
            text="✓ Auto-download results",
            variable=self.auto_download_var
        )
        download_check.grid(row=3, column=0, padx=5, pady=5, sticky="w")
        
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
            # Remove account from accounts.json
            if self.modifier.team_id:
                accounts_manager.remove_account(str(self.modifier.team_id))
                self.refresh_accounts_dropdown()
            
            messagebox.showinfo(
                "Success",
                "Account deleted successfully!\n\n"
                "The application will now close."
            )
            self.root.quit()
        else:
            try:
                err_text = response.text
            except Exception:
                err_text = f"HTTP {response.status_code}"
            raise Exception(f"Delete failed: {response.status_code} - {err_text}")
    
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
        # First: try to import old auth file if accounts.json doesn't exist
        if not accounts_manager.ACCOUNTS_FILE.exists() and config.AUTH_FILE.exists():
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
                return
        
        # Fallback: try old auth file directly
        if config.AUTH_FILE.exists():
            success = self.modifier.load_from_captured(str(config.AUTH_FILE))
            if success:
                self.auth_label.configure(text="Auth: ✅", text_color="green")
                self.refresh_credits()
                return
        
        self.auth_label.configure(text="Auth: ❌ No accounts", text_color="red")
    
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
                print(f"🔄 Switched to account: {account.get('label')}")
            else:
                self.auth_label.configure(text="Auth: ❌ Failed", text_color="red")
    
    def refresh_credits(self):
        """Refresh credits display (Runway accurate balance)"""
        try:
            credits = None
            # 1️⃣ Récupérer le team_id depuis le profile
            profile_resp = self.modifier.session.get(
                f"{self.modifier.base_url}/v1/profile"
            )
            if profile_resp.status_code != 200:
                raise Exception("Profile fetch failed")
            profile_data = profile_resp.json()
            user = profile_data.get("user", {})
            team_id = user.get("id")
            if not team_id:
                raise Exception("Team ID introuvable")
            # 2️⃣ Crédit réel AVEC asTeamId
            usage_resp = self.modifier.session.get(
                f"{self.modifier.base_url}/v1/billing/credits_usages",
                params={"asTeamId": team_id}
            )
            if usage_resp.status_code == 200:
                usage_data = usage_resp.json()
                usages = usage_data.get("creditUsages", [])
                if usages:
                    credits = usages[0].get("newBalance")
            # 3️⃣ Fallback (compte neuf)
            if credits is None:
                credits = user.get("gpuCredits", 0)
            print(f"✅ Crédit réel: {credits} | Team: {team_id}")
            # Save cache
            self.cache.save_profile(team_id, credits)
            # Update UI
            self.credits_label.configure(text=f"Credits: {credits} ⚡")
        except Exception as e:
            print(f"❌ Error refreshing credits: {e}")
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
            filetypes=[("Images", "*.jpg *.jpeg *.png *.webp")]
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
            
            # Filename
            filename = os.path.basename(item['file'])
            cache_tag = " [CACHED]" if item.get('from_cache') else ""
            error_tag = f" - {item.get('error', '')}" if item.get('error') else ""
            
            ctk.CTkLabel(
                frame, 
                text=f"{filename}{cache_tag}{error_tag}",
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
    
    def clear_queue(self):
        """Clear queue"""
        if not self.processing:
            self.queue = []
            self.current_index = 0
            self.update_queue_display()
    
    def start_batch(self):
        """Start batch processing"""
        if not self.queue:
            messagebox.showwarning("Empty Queue", "Add some images first!")
            return
        
        if not self.prompt_entry.get():
            messagebox.showwarning("No Prompt", "Enter a prompt first!")
            return
        
        # Reset index for new batch
        self.current_index = 0
        
        self.processing = True
        self.paused = False
        self.start_btn.configure(state="disabled")
        self.pause_btn.configure(state="normal")
        self.stop_btn.configure(state="normal")
        
        threading.Thread(target=self.process_batch, daemon=True).start()
    
    def process_batch(self):
        """Process batch with intelligent error handling"""
        total = len(self.queue)
        success_count = 0
        failed_count = 0
        skipped_count = 0
        
        # Error log file
        error_log_path = config.OUTPUTS_DIR / f"errors_{time.strftime('%Y%m%d_%H%M%S')}.log"
        
        for idx in range(self.current_index, total):
            if not self.processing:
                break
            
            while self.paused:
                time.sleep(0.1)
            
            if not self.processing:
                break
            
            item = self.queue[idx]
            self.current_index = idx
            filename = os.path.basename(item['file'])
            
            # Update progress
            progress = (idx + 1) / total
            self.progress_bar.set(progress)
            self.progress_label.configure(text=f"Processing {idx + 1}/{total}: {filename}")
            
            # Mark as processing
            item['status'] = 'processing'
            self.root.after(0, self.update_queue_display)
            
            try:
                # 1. Check cache / Upload
                if self.use_cache_var.get():
                    cached = self.cache.check_cached_upload(item['file'])
                    if cached:
                        asset = cached
                        print(f"✅ Using cached upload for {filename}")
                    else:
                        asset = self.upload_and_cache(item['file'])
                else:
                    asset = self.upload_and_cache(item['file'])
                
                # 2. Create AI task
                reference_images = [{
                    "assetId": asset['assetId'],
                    "url": asset['url'],
                    "tag": "IMG_1"
                }]
                
                # Get task type based on model
                model = self.model_var.get()
                if model == "ref_image_to_image":
                    task_type = "ref_image_to_image"
                    seed = random.randint(1, 999999)
                elif model == "ref_image_to_image_turbo":
                    task_type = "ref_image_to_image_turbo"
                    seed = random.randint(1, 999999)
                else:
                    task_type = "gemini_image"
                    seed = None
                
                ai_task = self.modifier.create_ai_task(
                    prompt=self.prompt_entry.get(),
                    reference_images=reference_images,
                    aspect_ratio=self.ratio_var.get(),
                    num_images=1,
                    task_type=task_type,
                    seed=seed
                )
                
                if not ai_task:
                    raise Exception("Failed to create AI task")
                
                # 3. Wait for completion
                completed_task = self.modifier.wait_for_completion(
                    ai_task['id'],
                    max_wait=300
                )
                
                if not completed_task:
                    raise Exception("Task failed or timeout")
                
                # Check if task actually failed
                if completed_task.get('status') == 'FAILED':
                    error_info = completed_task.get('failure', {})
                    error_reason = error_info.get('reason', 'Unknown')
                    error_msg = error_info.get('errorMessage', 'No details')
                    raise Exception(f"{error_reason}: {error_msg}")
                
                # 4. Get results
                result_urls = self.modifier.get_result_urls(completed_task)
                
                if not result_urls:
                    raise Exception("No results generated")
                
                # 5. Download if enabled
                if self.auto_download_var.get():
                    self.download_results(item['file'], result_urls)
                
                # SUCCESS!
                item['status'] = 'success'
                item['result_urls'] = result_urls
                success_count += 1
                print(f"✅ SUCCESS: {filename}")
                
            except Exception as e:
                # FAILED - but continue with next image!
                error_str = str(e)
                item['status'] = 'failed'
                item['error'] = error_str[:50]  # Truncate for display
                failed_count += 1
                
                # Log error to file
                with open(error_log_path, 'a', encoding='utf-8') as f:
                    f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {filename}\n")
                    f.write(f"  Error: {error_str}\n\n")
                
                print(f"❌ FAILED: {filename} - {error_str}")
                
                # Continue with next image - DON'T STOP!
            
            # Update display
            self.root.after(0, self.update_queue_display)
        
        # BATCH COMPLETE - show summary
        self.processing = False
        self.start_btn.configure(state="normal")
        self.pause_btn.configure(state="disabled")
        self.stop_btn.configure(state="disabled")
        
        # Final summary
        summary = f"Batch Complete!\n\n"
        summary += f"✅ Success: {success_count}\n"
        summary += f"❌ Failed: {failed_count}\n"
        
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
            raise Exception("Upload failed")
        
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
