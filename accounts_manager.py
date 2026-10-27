"""
Accounts Manager - Gestion multi-comptes Runway ML
Structure: accounts.json groupé par team_id
"""
import json
import re
import os
import base64
from datetime import datetime
from pathlib import Path
import config


ACCOUNTS_FILE = Path(config.DATA_DIR) / "accounts.json"


def load_accounts() -> dict:
    """Charge le fichier accounts.json"""
    if ACCOUNTS_FILE.exists():
        with open(ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"accounts": {}, "active_account": None}


def save_accounts(data: dict):
    """Sauvegarde le fichier accounts.json"""
    with open(ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def decode_jwt_payload(auth_header: str) -> dict:
    """Décode le payload d'un JWT Bearer sans vérifier la signature."""
    if not auth_header or "Bearer " not in auth_header:
        return {}

    token = auth_header.replace("Bearer ", "", 1).strip()
    parts = token.split(".")
    if len(parts) < 2:
        return {}

    payload = parts[1]
    padding = "=" * (-len(payload) % 4)

    try:
        decoded = base64.urlsafe_b64decode(payload + padding)
        data = json.loads(decoded.decode("utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    return {}


def parse_requests_to_accounts(requests_list: list) -> dict:
    """
    Analyse une liste de requêtes capturées et extrait les comptes.
    Retourne un dict {team_id: account_data}
    """
    accounts = {}

    for req in requests_list:
        headers = req.get('headers', {})
        url = req.get('url', '')
        body = req.get('request_body', {})
        if not isinstance(body, dict):
            body = {}

        # Récupère l'authorization
        auth = headers.get('authorization') or headers.get('Authorization') or req.get('authorization')
        if not auth or 'Bearer' not in auth:
            continue

        # Récupère le team_id
        team_id = None

        # Dans le body (asTeamId)
        if 'asTeamId' in body:
            team_id = int(body['asTeamId'])

        # Dans l'URL
        if not team_id and 'asTeamId=' in url:
            match = re.search(r'asTeamId=(\d+)', url)
            if match:
                team_id = int(match.group(1))

        # Dans les headers x-runway-workspace
        if not team_id:
            workspace = headers.get('x-runway-workspace')
            if workspace and workspace.isdigit():
                team_id = int(workspace)

        if not team_id:
            continue

        team_key = str(team_id)

        if team_key not in accounts:
            accounts[team_key] = {
                "team_id": team_id,
                "label": f"Account {team_id}",
                "email": "",
                "first_name": "",
                "last_name": "",
                "authorization": auth,
                "asset_group_id": None,
                "session_id": None,
                "captured_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "extra_headers": {}
            }
        else:
            # Toujours mettre à jour le token (le plus récent = le meilleur)
            accounts[team_key]["authorization"] = auth
            accounts[team_key]["captured_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        acc = accounts[team_key]

        # Fallback: l'email est souvent présent dans le JWT, même sans /v1/profile
        if not acc["email"]:
            jwt_payload = decode_jwt_payload(auth)
            jwt_email = jwt_payload.get("email")
            if jwt_email:
                acc["email"] = jwt_email
                acc["label"] = jwt_email

        # Asset Group ID
        if 'assetGroupId' in body and not acc["asset_group_id"]:
            acc["asset_group_id"] = body['assetGroupId']

        # Session ID
        if 'sessionId' in body and not acc["session_id"]:
            acc["session_id"] = body['sessionId']
        elif '/sessions/' in url and not acc["session_id"]:
            match = re.search(r'/sessions/([a-f0-9-]+)', url)
            if match:
                acc["session_id"] = match.group(1)

        # Extra headers utiles
        for h in ['x-session-id', 'x-runway-version', 'user-agent']:
            if h in headers:
                acc["extra_headers"][h] = headers[h]

        # Email depuis response profile
        resp = req.get('response', {})
        if resp and '/v1/profile' in url:
            resp_body = resp.get('body', {})
            if isinstance(resp_body, dict):
                user = resp_body.get('user', {})
                if user.get('email'):
                    acc["email"] = user['email']
                    first = user.get('firstName', '')
                    last = user.get('lastName', '')
                    acc["first_name"] = first
                    acc["last_name"] = last
                    if first or last:
                        acc["label"] = f"{first} {last}".strip() + f" ({user['email']})"
                    else:
                        acc["label"] = user['email']

    return accounts


def merge_accounts_into_file(new_accounts: dict):
    """
    Fusionne les nouveaux comptes dans accounts.json
    (ne supprime pas les comptes existants)
    """
    data = load_accounts()

    for team_key, account in new_accounts.items():
        if team_key in data["accounts"]:
            # Mise à jour du token et des infos
            existing = data["accounts"][team_key]
            existing["authorization"] = account["authorization"]
            existing["captured_at"] = account["captured_at"]
            # Mise à jour email/label si détectés
            if account["email"]:
                existing["email"] = account["email"]
                existing["label"] = account["label"]
            # Mise à jour session/asset_group si trouvés
            if account["asset_group_id"]:
                existing["asset_group_id"] = account["asset_group_id"]
            if account["session_id"]:
                existing["session_id"] = account["session_id"]
            existing["extra_headers"].update(account["extra_headers"])
            print(f"✅ Updated account: {existing['label']} (ID: {team_key})")
        else:
            # Nouveau compte
            data["accounts"][team_key] = account
            print(f"✅ New account added: {account['label']} (ID: {team_key})")

    # Activer automatiquement si c'est le premier compte
    if data["active_account"] is None and data["accounts"]:
        data["active_account"] = list(data["accounts"].keys())[0]

    save_accounts(data)
    return data


def list_accounts() -> list:
    """Retourne la liste des comptes [{team_id, label, ...}]"""
    data = load_accounts()
    return list(data["accounts"].values())


def get_account(team_id: str) -> dict:
    """Retourne les infos d'un compte spécifique"""
    data = load_accounts()
    return data["accounts"].get(str(team_id))


def get_active_account() -> dict:
    """Retourne le compte actif"""
    data = load_accounts()
    active_id = data.get("active_account")
    if active_id and active_id in data["accounts"]:
        return data["accounts"][active_id]
    # Fallback au premier compte
    if data["accounts"]:
        return list(data["accounts"].values())[0]
    return None


def set_active_account(team_id: str):
    """Définit le compte actif"""
    data = load_accounts()
    if str(team_id) in data["accounts"]:
        data["active_account"] = str(team_id)
        save_accounts(data)
        return True
    return False


def remove_account(team_id: str):
    """Supprime un compte du fichier"""
    data = load_accounts()
    team_key = str(team_id)
    if team_key in data["accounts"]:
        del data["accounts"][team_key]
        # Si c'était le compte actif, reset
        if data["active_account"] == team_key:
            data["active_account"] = list(data["accounts"].keys())[0] if data["accounts"] else None
        save_accounts(data)
        return True
    return False


def import_from_old_auth_file(auth_file: str) -> int:
    """
    Import legacy runway_auth.json vers accounts.json
    Retourne le nombre de comptes trouvés
    """
    try:
        with open(auth_file, 'r', encoding='utf-8') as f:
            requests_list = json.load(f)

        new_accounts = parse_requests_to_accounts(requests_list)

        if new_accounts:
            merge_accounts_into_file(new_accounts)
            return len(new_accounts)
        return 0
    except Exception as e:
        print(f"❌ Error importing old auth: {e}")
        return 0
