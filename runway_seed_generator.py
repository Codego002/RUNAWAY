"""
Runway ML Seed Generator
Génère des seeds aléatoires pour Gen4 et Gen4Turbo
(Gemini n'utilise PAS de seed!)
"""
import random


class RunwaySeedGenerator:
    """Génère des seeds pour les modèles Runway"""
    
    @staticmethod
    def generate_seed():
        """
        Génère un seed aléatoire (6 chiffres)
        Utilisé par Gen4 et Gen4Turbo SEULEMENT
        """
        return random.randint(100000, 999999)
    
    @staticmethod
    def model_uses_seed(task_type: str) -> bool:
        """
        Vérifie si un modèle utilise seed
        
        Args:
            task_type: Type de tâche (ex: "ref_image_to_image")
        
        Returns:
            True si le modèle utilise seed
        """
        seed_models = [
            "ref_image_to_image",        # Gen4
            "ref_image_to_image_turbo"   # Gen4Turbo
        ]
        return task_type in seed_models
    
    @staticmethod
    def build_gen4_request(
        text_prompt: str,
        asset_id: str,
        width: int = 1088,
        height: int = 1456,
        explore_mode: bool = False,
        asset_group_id: str = None,
        session_id: str = None,
        team_id: int = None
    ) -> dict:
        """
        Construit une requête Gen4 AVEC seed
        
        Args:
            text_prompt: Prompt texte
            asset_id: ID de l'image de référence
            width: Largeur
            height: Hauteur
            explore_mode: Mode exploration
            asset_group_id: ID du groupe d'assets
            session_id: ID de la session
            team_id: ID de l'équipe
        
        Returns:
            Dict de la requête complète
        """
        seed = RunwaySeedGenerator.generate_seed()
        
        request = {
            "taskType": "ref_image_to_image",
            "options": {
                "name": f"Gen4 {text_prompt}",
                "text_prompt": text_prompt,
                "width": width,
                "height": height,
                "num_images": 1,
                "seed": seed,  # ← SEED GÉNÉRÉ
                "exploreMode": explore_mode,
                "flip": True,
                "reference_images": [{
                    "assetId": asset_id
                }]
            }
        }
        
        # Ajouter les champs optionnels
        if asset_group_id:
            request["options"]["assetGroupId"] = asset_group_id
        
        if session_id:
            request["asTeamId"] = team_id or 0
            request["sessionId"] = session_id
        
        return request
    
    @staticmethod
    def build_gen4_turbo_request(
        text_prompt: str,
        asset_id: str,
        width: int = 1088,
        height: int = 1456,
        explore_mode: bool = False,
        asset_group_id: str = None,
        session_id: str = None,
        team_id: int = None
    ) -> dict:
        """
        Construit une requête Gen4Turbo AVEC seed
        
        Args:
            text_prompt: Prompt texte
            asset_id: ID de l'image de référence
            width: Largeur
            height: Hauteur
            explore_mode: Mode exploration
            asset_group_id: ID du groupe d'assets
            session_id: ID de la session
            team_id: ID de l'équipe
        
        Returns:
            Dict de la requête complète
        """
        seed = RunwaySeedGenerator.generate_seed()
        
        request = {
            "taskType": "ref_image_to_image_turbo",
            "options": {
                "name": f"Gen4Turbo {text_prompt}",
                "text_prompt": text_prompt,
                "width": width,
                "height": height,
                "num_images": 1,
                "seed": seed,  # ← SEED GÉNÉRÉ
                "exploreMode": explore_mode,
                "reference_images": [{
                    "assetId": asset_id
                }]
            }
        }
        
        # Ajouter les champs optionnels
        if asset_group_id:
            request["options"]["assetGroupId"] = asset_group_id
        
        if session_id:
            request["asTeamId"] = team_id or 0
            request["sessionId"] = session_id
        
        return request
    
    @staticmethod
    def build_gemini_request(
        text_prompt: str,
        asset_id: str,
        width: int = 1088,
        height: int = 1456,
        asset_group_id: str = None,
        session_id: str = None,
        team_id: int = None
    ) -> dict:
        """
        Construit une requête Gemini SANS seed
        
        Args:
            text_prompt: Prompt texte
            asset_id: ID de l'image de référence
            width: Largeur
            height: Hauteur
            asset_group_id: ID du groupe d'assets
            session_id: ID de la session
            team_id: ID de l'équipe
        
        Returns:
            Dict de la requête complète
        """
        request = {
            "taskType": "gemini_image",
            "options": {
                "name": f"Gemini {text_prompt}",
                "prompt": text_prompt,
                "width": width,
                "height": height,
                "num_images": 1,
                "reference_image": {
                    "assetId": asset_id
                }
            }
        }
        
        # Ajouter les champs optionnels
        if asset_group_id:
            request["options"]["assetGroupId"] = asset_group_id
        
        if session_id:
            request["asTeamId"] = team_id or 0
            request["sessionId"] = session_id
        
        return request


# ============ EXEMPLE D'UTILISATION ============

if __name__ == "__main__":
    gen = RunwaySeedGenerator()
    
    print("🎲 Génération de seeds aléatoires:\n")
    
    # Test 1: Seed simple
    print(f"Seed aléatoire: {gen.generate_seed()}")
    print(f"Seed aléatoire: {gen.generate_seed()}")
    print(f"Seed aléatoire: {gen.generate_seed()}\n")
    
    # Test 2: Vérifier modèles
    print("📊 Modèles qui utilisent seed:")
    print(f"  ref_image_to_image: {gen.model_uses_seed('ref_image_to_image')}")
    print(f"  ref_image_to_image_turbo: {gen.model_uses_seed('ref_image_to_image_turbo')}")
    print(f"  gemini_image: {gen.model_uses_seed('gemini_image')}\n")
    
    # Test 3: Requête Gen4
    print("🎬 Exemple requête Gen4 (avec seed):")
    req_gen4 = gen.build_gen4_request(
        text_prompt="Une voiture sur la route",
        asset_id="da0247c5-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    )
    print(f"  Seed généré: {req_gen4['options']['seed']}")
    print(f"  Task type: {req_gen4['taskType']}\n")
    
    # Test 4: Requête Gen4Turbo
    print("⚡ Exemple requête Gen4Turbo (avec seed):")
    req_turbo = gen.build_gen4_turbo_request(
        text_prompt="Un paysage de montagne",
        asset_id="7f8e9a1b-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    )
    print(f"  Seed généré: {req_turbo['options']['seed']}")
    print(f"  Task type: {req_turbo['taskType']}\n")
    
    # Test 5: Requête Gemini
    print("🔮 Exemple requête Gemini (SANS seed):")
    req_gemini = gen.build_gemini_request(
        text_prompt="Un coucher de soleil",
        asset_id="a1b2c3d4-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    )
    print(f"  Seed présent: {'seed' in req_gemini['options']}")
    print(f"  Task type: {req_gemini['taskType']}")
    
    print("\n✅ Tous les tests passés!")
