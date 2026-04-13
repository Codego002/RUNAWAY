"""
Runway ML AI Image Modifier
Automatise la modification d'images via l'IA de Runway ML
"""
import requests
import json
import time
import os
from typing import Optional, Dict, Any, List
from runway_uploader import RunwayUploader


class RunwayAIModifier:
    def __init__(self, bearer_token: str = None):
        """
        Initialize Runway AI Modifier
        
        Args:
            bearer_token: Bearer token pour l'authentification
        """
        self.base_url = "https://api.runwayml.com"
        self.bearer_token = bearer_token
        
        # Headers
        self.headers = {
            "Authorization": f"Bearer {bearer_token}" if bearer_token else "",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-runway-source-application": "web",
            "Origin": "https://app.runwayml.com",
            "Referer": "https://app.runwayml.com/",
        }
        
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        # Uploader pour les images
        self.uploader = RunwayUploader(bearer_token=bearer_token)
        
        # IDs extraits
        self.team_id = None
        self.asset_group_id = None
        self.session_id = None
    
    def load_from_captured(self, json_file: str) -> bool:
        """
        Charge les IDs depuis les requêtes capturées
        
        Args:
            json_file: Fichier JSON des requêtes capturées
            
        Returns:
            True si succès
        """
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                requests_data = json.load(f)
            
            # Parcourt toutes les requêtes pour extraire les infos
            # (prend le dernier token trouvé = le plus récent)
            for req in requests_data:
                headers = req.get('headers', {})
                url = req.get('url', '')
                # Support both 'body' and 'request_body' keys
                body = req.get('request_body', req.get('body', {}))
                if not isinstance(body, dict):
                    body = {}
                
                # Token (met à jour à chaque fois → on garde le plus récent)
                auth = headers.get('authorization') or headers.get('Authorization') or req.get('authorization')
                if auth and 'Bearer' in auth:
                    self.bearer_token = auth.replace('Bearer ', '')
                    self.headers['Authorization'] = auth
                    self.session.headers.update({'Authorization': auth})
                
                # Team ID
                if 'asTeamId=' in url and not self.team_id:
                    import re
                    match = re.search(r'asTeamId=(\d+)', url)
                    if match:
                        self.team_id = int(match.group(1))
                
                # Team ID depuis le body
                if 'asTeamId' in body and not self.team_id:
                    self.team_id = int(body['asTeamId'])
                
                # Team ID depuis headers workspace
                ws = headers.get('x-runway-workspace')
                if ws and ws.isdigit() and not self.team_id:
                    self.team_id = int(ws)
                
                # Asset Group ID
                if 'assetGroupId' in body and not self.asset_group_id:
                    self.asset_group_id = body['assetGroupId']
                
                # Session ID
                if 'sessionId' in body and not self.session_id:
                    self.session_id = body['sessionId']
                elif '/sessions/' in url and not self.session_id:
                    import re
                    match = re.search(r'/sessions/([a-f0-9-]+)', url)
                    if match:
                        self.session_id = match.group(1)
            
            if not self.bearer_token:
                print("❌ No Bearer token found in auth file!")
                return False
            
            print(f"✅ Token loaded")
            print(f"✅ Team ID: {self.team_id}")
            print(f"✅ Asset Group ID: {self.asset_group_id}")
            print(f"✅ Session ID: {self.session_id}")
            print(f"✅ Authorization header loaded: {self.headers['Authorization'][:50]}...")
            
            # Charge aussi dans l'uploader
            self.uploader.load_auth_from_captured(json_file)
            
            return True
            
        except Exception as e:
            print(f"❌ Error loading from captured: {e}")
            return False
    
    def load_account_data(self, account: dict) -> bool:
        """
        Charge directement un compte depuis accounts.json
        
        Args:
            account: dict avec {authorization, team_id, asset_group_id, session_id, extra_headers}
            
        Returns:
            True si succès
        """
        try:
            auth = account.get("authorization", "")
            if not auth:
                print("❌ No authorization in account data")
                return False
            
            # Set bearer token
            self.bearer_token = auth.replace("Bearer ", "")
            self.headers["Authorization"] = auth
            self.session.headers.update({"Authorization": auth})
            
            # Set IDs
            self.team_id = account.get("team_id")
            self.asset_group_id = account.get("asset_group_id")
            self.session_id = account.get("session_id")
            
            # Apply extra headers
            extra = account.get("extra_headers", {})
            if extra:
                self.session.headers.update(extra)
            
            # Apply to uploader too
            self.uploader.headers.update({"Authorization": auth})
            self.uploader.session.headers.update({"Authorization": auth})
            if self.team_id:
                self.uploader.team_id = self.team_id
                self.session.headers['x-runway-workspace'] = str(self.team_id)
            
            label = account.get("label", f"Account {self.team_id}")
            print(f"✅ Account loaded: {label}")
            print(f"✅ Team ID: {self.team_id}")
            print(f"✅ Asset Group ID: {self.asset_group_id}")
            print(f"✅ Session ID: {self.session_id}")
            print(f"✅ Authorization: {auth[:40]}...")
            
            return True
            
        except Exception as e:
            print(f"❌ Error loading account data: {e}")
            return False
    
    def upload_image_for_ai(self, image_path: str) -> Optional[Dict[str, Any]]:
        """
        Upload une image et récupère son assetId pour l'IA
        
        Args:
            image_path: Chemin vers l'image
            
        Returns:
            Dict avec assetId et url
        """
        print(f"\n📤 Uploading image for AI: {image_path}")
        
        # Upload complet
        result = self.uploader.auto_upload(image_path, create_dataset=True)
        
        if not result or 'dataset' not in result:
            print("❌ Upload failed")
            return None
        
        dataset = result['dataset']
        
        return {
            "assetId": dataset.get('id'),
            "url": dataset.get('url'),
            "name": os.path.basename(image_path)
        }
    
    def create_ai_task(
        self,
        prompt: str,
        reference_images: List[Dict[str, str]],
        task_type: str = "gemini_image",
        aspect_ratio: str = "9:16",
        num_images: int = 1,
        name: str = None,
        seed: int = None
    ) -> Optional[Dict[str, Any]]:
        """
        Crée une tâche de modification d'image par IA
        
        Args:
            prompt: Le prompt pour l'IA
            reference_images: Liste de {assetId, url, tag}
            task_type: Type de tâche (gemini_image, ref_image_to_image, ref_image_to_image_turbo)
            aspect_ratio: Ratio de l'image (9:16, 1:1, 16:9)
            num_images: Nombre d'images à générer
            name: Nom de la tâche (optionnel)
            seed: Seed pour Gen4/Gen4Turbo
            
        Returns:
            Task info avec task_id
        """
        print(f"\n🎨 Creating AI task: {prompt}")
        print(f"📋 Task type: {task_type}")
        
        if not name:
            name = prompt[:50]
        
        # Calculate width/height from aspect_ratio
        aspect_map = {
            "9:16": (1088, 1456),
            "16:9": (1456, 1088),
            "1:1": (1088, 1088),
            "4:3": (1088, 1456),
            "3:4": (1088, 1456)
        }
        width, height = aspect_map.get(aspect_ratio, (1088, 1456))
        
        # Build payload based on task type
        is_gen4 = task_type in ["ref_image_to_image", "ref_image_to_image_turbo"]
        
        if is_gen4:
            # Gen4/Gen4Turbo format (no "workflow_" prefix)
            payload = {
                "taskType": task_type,
                "options": {
                    "name": name,
                    "text_prompt": prompt,
                    "width": width,
                    "height": height,
                    "num_images": num_images,
                    "exploreMode": False,
                    "reference_images": reference_images,
                    "flip": True
                }
            }
            
            # Add seed if provided
            if seed is not None:
                payload["options"]["seed"] = seed
                print(f"🎲 Using seed: {seed}")
        else:
            # Gemini format (with "workflow_" prefix)
            payload = {
                "taskType": f"workflow_{task_type}",
                "options": {
                    "name": name,
                    "text_prompt": prompt,
                    "aspect_ratio": aspect_ratio,
                    "num_images": num_images,
                    "exploreMode": False,
                    "reference_images": reference_images
                }
            }
        
        # Ajoute les IDs si disponibles
        if self.asset_group_id:
            payload["options"]["assetGroupId"] = self.asset_group_id
        
        if self.team_id:
            payload["asTeamId"] = self.team_id
            self.session.headers['x-runway-workspace'] = str(self.team_id)
        
        if self.session_id:
            payload["sessionId"] = self.session_id
        
        try:
            print(f"📤 Payload: {payload}")
            
            response = self.session.post(
                f"{self.base_url}/v1/tasks",
                json=payload
            )
            
            print(f"Status: {response.status_code}")
            
            if response.status_code not in [200, 201]:
                print(f"❌ Failed to create task: {response.text}")
                return None
            
            result = response.json()
            task = result.get('task', result)
            
            task_id = task.get('id')
            status = task.get('status')
            
            print(f"✅ Task created!")
            print(f"Task ID: {task_id}")
            print(f"Status: {status}")
            
            return task
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Récupère le status d'une tâche
        
        Args:
            task_id: ID de la tâche
            
        Returns:
            Task info avec status et artifacts
        """
        try:
            url = f"{self.base_url}/v1/tasks/{task_id}"
            
            if self.team_id:
                url += f"?asTeamId={self.team_id}"
            
            response = self.session.get(url)
            
            if response.status_code != 200:
                print(f"❌ Failed to get task: {response.text}")
                return None
            
            result = response.json()
            task = result.get('task', result)
            
            return task
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return None
    
    def wait_for_completion(
        self,
        task_id: str,
        max_wait: int = 300,
        poll_interval: int = 5
    ) -> Optional[Dict[str, Any]]:
        """
        Attend qu'une tâche soit complétée
        
        Args:
            task_id: ID de la tâche
            max_wait: Temps max d'attente en secondes
            poll_interval: Intervalle entre les checks en secondes
            
        Returns:
            Task complétée avec artifacts
        """
        print(f"\n⏳ Waiting for task completion...")
        print(f"Task ID: {task_id}")
        
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            task = self.get_task_status(task_id)
            
            if not task:
                time.sleep(poll_interval)
                continue
            
            status = task.get('status')
            progress = task.get('progressRatio', 0)
            
            print(f"  Status: {status} | Progress: {progress}")
            
            if status == "SUCCEEDED":
                print(f"✅ Task completed!")
                return task
            
            elif status == "FAILED":
                error = task.get('error', 'Unknown error')
                print(f"❌ Task failed: {error}")
                return None
            
            elif status in ["PENDING", "RUNNING"]:
                time.sleep(poll_interval)
            
            else:
                print(f"⚠️  Unknown status: {status}")
                time.sleep(poll_interval)
        
        print(f"❌ Timeout after {max_wait}s")
        return None
    
    def get_result_urls(self, task: Dict[str, Any]) -> List[str]:
        """
        Extrait les URLs des résultats d'une tâche
        
        Args:
            task: Task complétée
            
        Returns:
            Liste des URLs des images générées
        """
        artifacts = task.get('artifacts', [])
        urls = []
        
        for artifact in artifacts:
            url = artifact.get('url')
            if url:
                urls.append(url)
                print(f"  🎨 Result: {url}")
        
        return urls
    
    def modify_image(
        self,
        image_path: str,
        prompt: str,
        aspect_ratio: str = "9:16",
        num_images: int = 1,
        wait: bool = True
    ) -> Optional[List[str]]:
        """
        Modifie une image avec l'IA (workflow complet)
        
        Args:
            image_path: Chemin vers l'image à modifier
            prompt: Prompt pour l'IA
            aspect_ratio: Ratio de sortie
            num_images: Nombre d'images à générer
            wait: Attendre la complétion ?
            
        Returns:
            Liste des URLs des résultats
        """
        print("\n" + "="*80)
        print("🎨 RUNWAY AI IMAGE MODIFICATION")
        print("="*80)
        
        # 1. Upload l'image
        asset = self.upload_image_for_ai(image_path)
        
        if not asset:
            return None
        
        # 2. Crée la tâche AI
        reference_images = [{
            "assetId": asset['assetId'],
            "url": asset['url'],
            "tag": "IMG_1"
        }]
        
        task = self.create_ai_task(
            prompt=prompt,
            reference_images=reference_images,
            aspect_ratio=aspect_ratio,
            num_images=num_images
        )
        
        if not task:
            return None
        
        task_id = task.get('id')
        
        # 3. Attends la complétion
        if wait:
            completed_task = self.wait_for_completion(task_id)
            
            if not completed_task:
                return None
            
            # 4. Récupère les résultats
            urls = self.get_result_urls(completed_task)
            
            print("\n" + "="*80)
            print(f"✅ MODIFICATION COMPLETE - {len(urls)} result(s)")
            print("="*80 + "\n")
            
            return urls
        else:
            print(f"\n⏳ Task started: {task_id}")
            print("Check status later with get_task_status()")
            return [task_id]


def main():
    """Demo usage"""
    import sys
    
    import config
    
    print("\n" + "="*80)
    print("🎨 RUNWAY AI IMAGE MODIFIER")
    print("="*80 + "\n")
    
    # Charge depuis le fichier capturé
    if not config.AUTH_FILE.exists():
        print("❌ No auth file found!")
        print("Run mitmdump first to capture authentication")
        return
    
    print(f"📁 Loading from: {config.AUTH_FILE}\n")
    
    # Initialize
    modifier = RunwayAIModifier()
    modifier.load_from_captured(str(config.AUTH_FILE))
    
    # Usage
    if len(sys.argv) < 3:
        print("\nUsage:")
        print("  python runway_ai_modifier.py <image> <prompt>")
        print()
        print("Examples:")
        print('  python runway_ai_modifier.py photo.jpg "change the background"')
        print('  python runway_ai_modifier.py selfie.jpg "make it artistic"')
        print('  python runway_ai_modifier.py img.jpg "add sunglasses" --ratio 1:1')
        return
    
    image_path = sys.argv[1]
    prompt = sys.argv[2]
    
    # Options
    aspect_ratio = "9:16"
    if '--ratio' in sys.argv:
        idx = sys.argv.index('--ratio')
        aspect_ratio = sys.argv[idx + 1]
    
    num_images = 1
    if '--num' in sys.argv:
        idx = sys.argv.index('--num')
        num_images = int(sys.argv[idx + 1])
    
    # Modify
    result_urls = modifier.modify_image(
        image_path=image_path,
        prompt=prompt,
        aspect_ratio=aspect_ratio,
        num_images=num_images
    )
    
    if result_urls:
        print("\n🎉 Success!")
        print("\nResult URLs:")
        for i, url in enumerate(result_urls, 1):
            print(f"{i}. {url}")
        print()


if __name__ == "__main__":
    main()
