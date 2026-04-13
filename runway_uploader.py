"""
Runway ML Image Uploader
Script d'upload automatisé basé sur l'analyse des requêtes capturées
"""
import requests
import json
import os
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
            print(f"❌ File not found: {image_path}")
            return None
        
        print(f"\n📤 Uploading: {image_path}")
        
        try:
            filename = os.path.basename(image_path)
            file_size = os.path.getsize(image_path)
            
            # Calcule le nombre de parts (5MB par part pour les gros fichiers)
            part_size = 5 * 1024 * 1024  # 5MB
            num_parts = max(1, (file_size + part_size - 1) // part_size)
            
            # Step 1: Initie l'upload multipart
            print(f"Step 1: Initiating multipart upload ({num_parts} parts)...")
            
            init_payload = {
                "filename": filename,
                "numberOfParts": num_parts,
                "type": "DATASET"  # CRITICAL: Must be "DATASET" not "image"
            }
            
            response = self.session.post(
                f"{self.base_url}/v1/uploads",
                json=init_payload
            )
            
            print(f"Status: {response.status_code}")
            
            if response.status_code not in [200, 201]:
                print(f"❌ Failed to initiate upload: {response.text}")
                return None
            
            init_data = response.json()
            upload_id = init_data.get('id')
            upload_urls = init_data.get('uploadUrls', [])
            upload_headers = init_data.get('uploadHeaders', {})
            
            if not upload_id or not upload_urls:
                print(f"❌ Invalid response: {init_data}")
                return None
            
            print(f"✅ Upload ID: {upload_id}")
            print(f"✅ Got {len(upload_urls)} upload URL(s)")
            
            # Step 2: Upload chaque part vers S3
            print(f"Step 2: Uploading {num_parts} part(s) to S3...")
            
            parts = []
            with open(image_path, 'rb') as f:
                for i, upload_url in enumerate(upload_urls, 1):
                    # Lit la part
                    part_data = f.read(part_size)
                    if not part_data:
                        break
                    
                    print(f"  Uploading part {i}/{num_parts} ({len(part_data)} bytes)...")
                    
                    # Utilise les headers de la response
                    s3_headers = upload_headers.copy() if upload_headers else {}
                    if not s3_headers.get('Content-Type'):
                        mime_type, _ = mimetypes.guess_type(image_path)
                        s3_headers['Content-Type'] = mime_type or 'image/jpeg'
                    
                    # Upload vers S3
                    s3_response = requests.put(
                        upload_url,
                        data=part_data,
                        headers=s3_headers
                    )
                    
                    if s3_response.status_code not in [200, 204]:
                        print(f"❌ Failed to upload part {i}: {s3_response.status_code}")
                        return None
                    
                    # Récupère l'ETag
                    etag = s3_response.headers.get('ETag', '').strip('"')
                    parts.append({
                        "PartNumber": i,
                        "ETag": etag
                    })
                    
                    print(f"  ✅ Part {i} uploaded (ETag: {etag[:20]}...)")
            
            # Step 3: Complete l'upload
            print(f"Step 3: Completing upload...")
            
            complete_payload = {
                "parts": parts
            }
            
            complete_response = self.session.post(
                f"{self.base_url}/v1/uploads/{upload_id}/complete",
                json=complete_payload
            )
            
            print(f"Status: {complete_response.status_code}")
            
            if complete_response.status_code not in [200, 201]:
                print(f"❌ Failed to complete upload: {complete_response.text}")
                return None
            
            complete_data = complete_response.json()
            print(f"✅ Upload completed!")
            
            return {
                "upload_id": upload_id,
                "complete_response": complete_data
            }
            
        except Exception as e:
            print(f"❌ Error: {e}")
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
            
            # Extrait le teamId depuis les headers si disponible
            team_id = None
            for req in getattr(self, '_captured_requests', []):
                if 'asTeamId' in req.get('url', ''):
                    import re
                    match = re.search(r'asTeamId=(\d+)', req['url'])
                    if match:
                        team_id = int(match.group(1))
                        break
            
            payload = {
                "fileCount": 1,
                "name": filename,
                "uploadId": upload_id,
                "previewUploadIds": preview_upload_ids or [upload_id],
                "metadata": metadata,
                "type": {
                    "name": "image",
                    "type": "image",
                    "isDirectory": False
                }
            }
            
            # Ajoute asTeamId si trouvé
            if team_id:
                payload["asTeamId"] = team_id
                print(f"  Using Team ID: {team_id}")
            
            response = self.session.post(
                f"{self.base_url}/v1/datasets",
                json=payload
            )
            
            print(f"Status: {response.status_code}")
            
            if response.status_code not in [200, 201]:
                print(f"❌ Failed to create dataset: {response.text}")
                return None
            
            result = response.json()
            dataset = result.get('dataset', result)
            print(f"✅ Dataset created!")
            print(f"Dataset ID: {dataset.get('id', 'N/A')}")
            
            return dataset
            
        except Exception as e:
            print(f"❌ Error: {e}")
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
        
        # Upload multipart
        result = self.upload_image_multipart(image_path)
        
        if not result:
            print("\n❌ Upload failed!")
            return None
        
        # Crée le dataset si demandé
        if create_dataset:
            dataset = self.create_dataset(
                upload_id=result['upload_id'],
                filename=os.path.basename(image_path),
                image_path=image_path
            )
            
            if dataset:
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
