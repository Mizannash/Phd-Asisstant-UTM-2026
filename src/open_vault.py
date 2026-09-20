import os
import urllib.parse
import webbrowser
import yaml

def get_vault_name_from_config():
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "settings.yaml")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            settings = yaml.safe_load(f)
            return settings.get("vault_name") if settings else None
    except Exception:
        return None

def launch_obsidian():
    vault_name = get_vault_name_from_config()
    if vault_name:
        encoded_vault = urllib.parse.quote(vault_name, safe="")
        uri = f"obsidian://open?vault={encoded_vault}"
        print(f"Opening Obsidian Vault: {vault_name}")
        webbrowser.open(uri)
        return
        
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    vault_path = os.path.join(base_dir, "output", "Obsidian_Vault")
    
    if not os.path.exists(vault_path):
        os.makedirs(vault_path)
        
    clean_path = vault_path.replace("\\", "/")
    encoded_path = urllib.parse.quote(clean_path, safe=":/")
    uri = f"obsidian://open?path={encoded_path}"
    
    print(f"Opening Obsidian Vault at: {clean_path}")
    webbrowser.open(uri)

def get_obsidian_uri(filename, vault_name=None):
    """Returns an obsidian:// URI for a specific file in the vault."""
    vault_name = vault_name or get_vault_name_from_config()
    
    if vault_name:
        encoded_vault = urllib.parse.quote(vault_name, safe="")
        encoded_file = urllib.parse.quote(filename.replace(".md", ""), safe="")
        return f"obsidian://open?vault={encoded_vault}&file={encoded_file}"
        
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    vault_path = os.path.join(base_dir, "output", "Obsidian_Vault")
    file_path = os.path.join(vault_path, filename)
    clean_path = file_path.replace("\\", "/")
    encoded_path = urllib.parse.quote(clean_path, safe=":/")
    return f"obsidian://open?path={encoded_path}"

if __name__ == '__main__':
    launch_obsidian()
