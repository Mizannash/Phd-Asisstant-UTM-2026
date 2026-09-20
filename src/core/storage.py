import os
import base64
from typing import Dict, Optional, List
from github import Github, GithubException
from src.core.config import get_secret

REPO_NAME = "Mizannash/Phd-Asisstant-UTM-2026"

TRACKED_FILES = [
    "data/library_state.json",
    "output/analytics/actual_calls.csv"
]
TRACKED_DIRS = [
    "output/reports"
]

class StorageHandler:
    _remote_shas: Dict[str, str] = {}

    @staticmethod
    def get_github_client() -> Optional[Github]:
        try:
            token = get_secret("GITHUB_TOKEN")
            if token:
                return Github(token)
        except Exception as e:
            print(f"[StorageHandler] Offline mode: {e}")
        return None

    @classmethod
    def pull_state(cls):
        """Fetch latest state from GitHub to local disk."""
        gh = cls.get_github_client()
        if not gh:
            print("[StorageHandler] Offline mode: Skipping pull_state, falling back to local disk.")
            return

        try:
            repo = gh.get_repo(REPO_NAME)
            print("[StorageHandler] Pulling state from remote...")
            
            for file_path in TRACKED_FILES:
                cls._pull_file(repo, file_path)
            
            for dir_path in TRACKED_DIRS:
                try:
                    contents = repo.get_contents(dir_path)
                    for content_file in contents:
                        if content_file.type == "file":
                            cls._pull_file(repo, content_file.path)
                except GithubException as e:
                    if e.status != 404:
                        raise e

            print("[StorageHandler] Successfully pulled state from remote.")
        except Exception as e:
            print(f"[StorageHandler] Error during pull_state: {e}. Falling back to local disk.")

    @classmethod
    def _pull_file(cls, repo, file_path: str):
        try:
            content = repo.get_contents(file_path)
            cls._remote_shas[file_path] = content.sha
            file_data = base64.b64decode(content.content)
            
            local_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), file_path)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            with open(local_path, "wb") as f:
                f.write(file_data)
            print(f"[StorageHandler] Pulled {file_path}")
        except GithubException as e:
            if e.status == 404:
                print(f"[StorageHandler] File {file_path} not found on remote, skipping.")
            else:
                raise e

    @classmethod
    def push_state(cls, commit_message: str = "Automated state update"):
        """Write state back to repo via a commit. Fail loudly if diverged."""
        gh = cls.get_github_client()
        if not gh:
            print("[StorageHandler] Offline mode: Skipping push_state.")
            return

        repo = gh.get_repo(REPO_NAME)
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        
        files_to_check = list(TRACKED_FILES)
        for dir_path in TRACKED_DIRS:
            local_dir = os.path.join(base_dir, dir_path)
            if os.path.exists(local_dir):
                for f in os.listdir(local_dir):
                    if os.path.isfile(os.path.join(local_dir, f)):
                        # Ensure forward slashes for github API
                        files_to_check.append(f"{dir_path}/{f}")

        print("[StorageHandler] Pushing state to remote...")
        for file_path in files_to_check:
            local_path = os.path.join(base_dir, file_path)
            if not os.path.exists(local_path):
                continue
                
            with open(local_path, "rb") as f:
                local_content = f.read()

            try:
                # ALWAYS PULL FIRST / CHECK SHA
                remote_sha = None
                try:
                    remote_content = repo.get_contents(file_path)
                    remote_sha = remote_content.sha
                except GithubException as e:
                    if e.status != 404:
                        raise e

                last_known_sha = cls._remote_shas.get(file_path)
                
                if remote_sha:
                    if not last_known_sha:
                        raise RuntimeError(f"CRITICAL ERROR: Remote file {file_path} exists but we have no local record of pulling it. Prevented overwrite.")
                    if remote_sha != last_known_sha:
                        raise RuntimeError(f"CRITICAL ERROR: Remote file {file_path} diverged. Expected SHA {last_known_sha}, got {remote_sha}. Failing loudly.")
                        
                    res = repo.update_file(file_path, commit_message, local_content, remote_sha)
                    cls._remote_shas[file_path] = res['content'].sha
                    print(f"[StorageHandler] Updated {file_path}")
                else:
                    if last_known_sha:
                        raise RuntimeError(f"CRITICAL ERROR: File {file_path} was deleted on remote but we are trying to create it from a known state.")
                    res = repo.create_file(file_path, commit_message, local_content)
                    cls._remote_shas[file_path] = res['content'].sha
                    print(f"[StorageHandler] Created {file_path}")
                    
            except Exception as e:
                print(f"[StorageHandler] Failed to push {file_path}: {e}")
                raise e
