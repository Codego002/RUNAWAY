"""
Runway ML Image Uploader
Script d'upload automatisé basé sur l'analyse des requêtes capturées
"""
import requests
import json
import os
import time
import base64
from pathlib import Path
import mimetypes
from typing import Optional, Dict, Any, List


class RunwayUploader:
    def __init__(self, api_key: str = None, bearer_token: str = None):
        """
        Initialize Runway ML uploader
        
        Args:
            api_key: API key from Runway ML dashboard
            bearer_token: Bearer token from captured requests
        """
        self.base_url = "https://api.runwayml.com"
        self.api_key = api_key
        self.bearer_token = bearer_token
        self._captured_requests = []  # Store captured requests for team_id extraction
        
        # Headers de base (à ajuster selon l'analyse)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": "https://app.runwayml.com",
            "Referer": "https://app.runwayml.com/",
            "x-runway-source-application": "web",
            "Content-Type": "application/json",
        }
        
        # Ajoute l'authentification si disponible
        if bearer_token:
            self.headers["Authorization"] = f"Bearer {bearer_token}"
        elif api_key:
            self.headers["X-API-Key"] = api_key
        
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.team_id = None
        self.last_error = None

    def token_error(self) -> Optional[str]:
        """None when the bearer token is still inside its exp window."""
        auth = self.session.headers.get("Authorization") or self.headers.get("Authorization") or ""
        if "Bearer " not in auth:
            return "Pas de token. Lance le Scanner et connecte-toi dans Runway."
        payload = auth.split(" ", 1)[1].split(".")
        if len(payload) < 2:
            return "Token illisible. Relance le Scanner."
        try:
            segment = payload[1] + "=" * (-len(payload[1]) % 4)
            data = json.loads(base64.urlsafe_b64decode(segment))
        except Exception:
            return "Token illisible. Relance le Scanner."
        exp = data.get("exp")
        if exp and float(exp) < time.time():
            when = time.strftime("%Y-%m-%d %H:%M", time.localtime(float(exp)))
            return f"Token expiré le {when}. Relance le Scanner et reconnecte le compte."
        return None

    def _fail(self, message: str) -> None:
        self.last_error = message
        print(f"❌ {message}")

    def _apply_team_header(self) -> Optional[int]:
        team_id = self._team_id()
        if team_id:
            self.session.headers["x-runway-workspace"] = str(team_id)
        return team_id

    def _team_id(self) -> Optional[int]:
        if getattr(self, "team_id", None):
            return int(self.team_id)
        for req in getattr(self, "_captured_requests", []):
            url = req.get("url", "")
            if "asTeamId=" not in url:
                continue
            import re
            match = re.search(r"asTeamId=(\d+)", url)
            if match:
                return int(match.group(1))
        return None
    
    def load_auth_from_captured(self, json_file: str) -> bool:
        """
        Charge l'authentification depuis un fichier de requêtes capturées
        
        Args:
            json_file: Fichier JSON des requêtes capturées
            
        Returns:
            True si l'authentification a été trouvée
        """
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                requests_data = json.load(f)
            
            # Store for later use (e.g., extracting team_id)
            self._captured_requests = requests_data
            
            # Cherche les headers d'authentification
            for req in requests_data:
                headers = req.get('headers', {})
                
                # Cherche Authorization header
                if 'Authorization' in headers or 'authorization' in headers:
                    auth = headers.get('Authorization') or headers.get('authorization')
                    self.headers['Authorization'] = auth
                    self.session.headers.update({'Authorization': auth})
                    print(f"✅ Authorization header loaded: {auth[:30]}...")
                    return True
                
                # Cherche API key
                if 'X-API-Key' in headers or 'x-api-key' in headers:
                    api_key = headers.get('X-API-Key') or headers.get('x-api-key')
                    self.headers['X-API-Key'] = api_key
                    self.session.headers.update({'X-API-Key': api_key})
                    print(f"✅ API Key loaded: {api_key[:30]}...")
                    return True
                
                # Autres headers d'auth possibles
                for key, value in headers.items():
                    if 'token' in key.lower() or 'auth' in key.lower():
                        self.headers[key] = value
                        self.session.headers.update({key: value})
                        print(f"✅ Auth header loaded: {key}: {value[:30]}...")
                        return True
            
            print("⚠️  No authentication headers found in captured requests")
            return False
            
        except Exception as e:
            print(f"❌ Error loading auth: {e}")
            return False
    
    def upload_image_multipart(self, image_path: str) -> Optional[Dict[str, Any]]:
        """
        Upload une image avec le flow multipart Runway ML
        
        Args:
            image_path: Chemin vers l'image
            
        Returns:
            Response JSON ou None
        """
        if not os.path.exists(image_path):
            self._fail(f"Fichier introuvable: {image_path}")
            return None
        
        print(f"\n📤 Uploading: {image_path}")
        # Kept for callers that upload a single DATASET. auto_upload sends preview + dataset.
        return self._upload_typed(image_path, "DATASET")

    def _upload_typed(self, image_path: str, upload_type: str) -> Optional[Dict[str, Any]]:
        """POST /v1/uploads, PUT the bytes to S3, POST /complete. upload_type is DATASET or DATASET_PREVIEW."""
        try:
            filename = os.path.basename(image_path)
            file_size = os.path.getsize(image_path)
            part_size = 5 * 1024 * 1024
            num_parts = max(1, (file_size + part_size - 1) // part_size)

            print(f"Step 1: {upload_type} ({num_parts} part(s))...")
            self._apply_team_header()
            response = self.session.post(
                f"{self.base_url}/v1/uploads",
                json={
                    "filename": filename,
                    "numberOfParts": num_parts,
                    "type": upload_type,
                },
            )
            print(f"Status: {response.status_code}")
            if response.status_code == 401:
                self._fail("Token refusé (401). Relance le Scanner et reconnecte le compte.")
                return None
            if response.status_code not in (200, 201):
                self._fail(f"Init {upload_type} {response.status_code}: {response.text[:180]}")
                return None

            init_data = response.json()
            upload_id = init_data.get("id")
            upload_urls = init_data.get("uploadUrls", [])
            upload_headers = init_data.get("uploadHeaders") or {}
            if not upload_id or not upload_urls:
                self._fail(f"Réponse upload invalide: {list(init_data)[:8]}")
                return None

            parts = []
            with open(image_path, "rb") as handle:
                for index, upload_url in enumerate(upload_urls, 1):
                    part_data = handle.read(part_size)
                    if not part_data:
                        break
                    s3_headers = dict(upload_headers)
                    if not s3_headers.get("Content-Type"):
                        mime_type, _ = mimetypes.guess_type(image_path)
                        s3_headers["Content-Type"] = mime_type or "image/jpeg"
                    s3_response = requests.put(upload_url, data=part_data, headers=s3_headers)
                    if s3_response.status_code not in (200, 204):
                        self._fail(f"S3 {upload_type} part {index}: {s3_response.status_code}")
                        return None
                    # The app keeps the quotes S3 puts around the ETag.
                    etag = s3_response.headers.get("ETag", "").strip()
                    if etag and not (etag.startswith('"') and etag.endswith('"')):
                        etag = f'"{etag.strip(chr(34))}"'
                    parts.append({"PartNumber": index, "ETag": etag})

            print(f"Step 3: Completing {upload_type}...")
            complete_response = self.session.post(
                f"{self.base_url}/v1/uploads/{upload_id}/complete",
                json={"parts": parts},
            )
            print(f"Status: {complete_response.status_code}")
            if complete_response.status_code not in (200, 201):
                self._fail(f"Complete {upload_type} {complete_response.status_code}: {complete_response.text[:180]}")
                return None
            complete_data = complete_response.json()
            return {
                "upload_id": upload_id,
                "url": complete_data.get("url"),
                "complete_response": complete_data,
            }
            
        except Exception as e:
            self._fail(f"Upload {upload_type}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def create_dataset(self, upload_id: str, filename: str, preview_upload_ids: List[str] = None, image_path: str = None) -> Optional[Dict[str, Any]]:
        """
        Crée un dataset à partir d'un upload
        
        Args:
            upload_id: ID de l'upload complété
            filename: Nom du fichier
            preview_upload_ids: IDs des previews (optionnel)
            image_path: Chemin de l'image pour extraire les dimensions
            
        Returns:
            Response JSON ou None
        """
        print(f"\nStep 4: Creating dataset...")
        
        try:
            # Extrait les dimensions de l'image si possible
            metadata = {}
            if image_path and os.path.exists(image_path):
                try:
                    from PIL import Image
                    with Image.open(image_path) as img:
                        metadata = {
                            "size": {
                                "width": img.width,
                                "height": img.height
                            }
                        }
                        print(f"  Image size: {img.width}x{img.height}")
                except ImportError:
                    # PIL pas installé, utilise une valeur par défaut
                    metadata = {
                        "size": {
                            "width": 1920,
                            "height": 1080
                        }
                    }
                except Exception as e:
                    print(f"  ⚠️  Could not get image dimensions: {e}")
                    metadata = {
                        "size": {
                            "width": 1920,
                            "height": 1080
                        }
                    }
            
            team_id = self._apply_team_header()
            payload = {
                "fileCount": 1,
                "name": filename,
                "uploadId": upload_id,
                "previewUploadIds": preview_upload_ids or [upload_id],
                "isUserUpload": True,
                "privateInTeam": True,
                "metadata": metadata,
                "type": {
                    "name": "image",
                    "type": "image",
                    "isDirectory": False
                }
            }
            params = None
            if team_id:
                payload["asTeamId"] = team_id
                params = {"asTeamId": team_id}
                print(f"  Using Team ID: {team_id}")

            response = self.session.post(
                f"{self.base_url}/v1/datasets",
                params=params,
                json=payload
            )
            
            print(f"Status: {response.status_code}")
            
            if response.status_code not in [200, 201]:
                self._fail(f"Dataset {response.status_code}: {response.text[:180]}")
                return None
            
            result = response.json()
            dataset = result.get('dataset', result)
            print(f"✅ Dataset created!")
            print(f"Dataset ID: {dataset.get('id', 'N/A')}")
            
            return dataset
            
        except Exception as e:
            self._fail(f"Dataset: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def auto_upload(self, image_path: str, create_dataset: bool = True) -> Optional[Dict[str, Any]]:
        """
        Upload une image avec le flow Runway ML correct
        
        Args:
            image_path: Chemin vers l'image
            create_dataset: Créer automatiquement le dataset (default: True)
            
        Returns:
            Response JSON avec upload_id et dataset info
        """
        print(f"\n🚀 AUTO UPLOAD: {image_path}")
        print("="*80)
        self.last_error = None

        expired = self.token_error()
        if expired:
            self._fail(expired)
            return None

        # The app uploads the same bytes twice: a preview, then the dataset.
        preview = self._upload_typed(image_path, "DATASET_PREVIEW")
        if not preview:
            return None
        result = self._upload_typed(image_path, "DATASET")
        if not result:
            return None
        
        # Crée le dataset si demandé
        if create_dataset:
            dataset = self.create_dataset(
                upload_id=result['upload_id'],
                filename=os.path.basename(image_path),
                preview_upload_ids=[preview["upload_id"]],
                image_path=image_path
            )
            
            if not dataset:
                return None
            result['dataset'] = dataset
        
        print("\n" + "="*80)
        print("✅ UPLOAD COMPLETE")
        print("="*80)
        
        return result


def main():
    """Demo et test du script"""
    import sys
    import config
    
    print("\n" + "="*80)
    print("🎬 RUNWAY ML IMAGE UPLOADER")
    print("="*80 + "\n")
    
    # Initialise l'uploader
    uploader = RunwayUploader()
    
    # Charge l'auth depuis le fichier capturé
    if config.AUTH_FILE.exists():
        print(f"📁 Found auth: {config.AUTH_FILE}")
        uploader.load_auth_from_captured(str(config.AUTH_FILE))
    else:
        print("⚠️  No captured requests found")
        print("Run mitmproxy first: mitmdump -s runway_scanner.py")
        print("Then use Runway ML app to upload an image")
        print()
    
    # Test avec une image si fournie
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        result = uploader.auto_upload(image_path)
        
        if result:
            print("\n" + "="*80)
            print("✅ UPLOAD SUCCESSFUL")
            print("="*80)
            print(json.dumps(result, indent=2))
        else:
            print("\n❌ Upload failed - check the error messages above")
    else:
        print("\nUsage: python runway_uploader.py <image_path>")
        print("Example: python runway_uploader.py /path/to/image.jpg")
        print()
        print("Or use the RunwayUploader class in your own script:")
        print("""
from runway_uploader import RunwayUploader

uploader = RunwayUploader(bearer_token="your_token_here")

# Upload with dataset creation
result = uploader.auto_upload("image.jpg", create_dataset=True)

# Or just upload without dataset
result = uploader.upload_image_multipart("image.jpg")

# Then create dataset manually
if result:
    dataset = uploader.create_dataset(
        upload_id=result['upload_id'],
        filename="image.jpg"
    )
""")


if __name__ == "__main__":
    main()
