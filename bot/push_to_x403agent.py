"""Helper script to push only database file to X403Agent repository"""
import subprocess
import os
import shutil
import tempfile
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_paths = [
    os.path.join(os.path.dirname(__file__), '..', 'server', '.env'),
    os.path.join(os.path.dirname(__file__), '..', '.env'),
]
for env_path in env_paths:
    if os.path.exists(env_path):
        load_dotenv(env_path)
        break

def push_database_to_x403agent(db_path="token_holders.db", github_token=None, github_username="Concorde89"):
    """
    Push only the database file to X403Agent repository
    Uses a clean git repository to avoid workflow file issues
    """
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        abs_db_path = os.path.join(script_dir, db_path)
        
        if not os.path.exists(abs_db_path):
            return {
                "success": False,
                "message": f"Database file not found: {abs_db_path}"
            }
        
        if not github_token:
            github_token = os.getenv('GITHUB_TOKEN')
            if not github_token:
                return {
                    "success": False,
                    "message": "GITHUB_TOKEN not found in environment"
                }
        
        # Create temporary directory for clean git repo
        temp_dir = tempfile.mkdtemp(prefix="x403agent_push_")
        
        try:
            # Initialize git repository
            subprocess.run(
                ["git", "init"],
                cwd=temp_dir,
                check=True,
                capture_output=True,
                timeout=10
            )
            
            # Configure git user
            subprocess.run(
                ["git", "config", "user.name", "X403 Bot"],
                cwd=temp_dir,
                check=True,
                capture_output=True,
                timeout=5
            )
            subprocess.run(
                ["git", "config", "user.email", "bot@x403.local"],
                cwd=temp_dir,
                check=True,
                capture_output=True,
                timeout=5
            )
            
            # Copy database file
            db_filename = os.path.basename(db_path)
            temp_db_path = os.path.join(temp_dir, db_filename)
            shutil.copy2(abs_db_path, temp_db_path)
            
            # Add and commit
            subprocess.run(
                ["git", "add", db_filename],
                cwd=temp_dir,
                check=True,
                capture_output=True,
                timeout=10
            )
            
            from datetime import datetime
            timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
            commit_message = f"Update token holders database - {timestamp}"
            
            subprocess.run(
                ["git", "commit", "-m", commit_message],
                cwd=temp_dir,
                check=True,
                capture_output=True,
                timeout=10
            )
            
            # Add remote and push
            repo_url = f"https://{github_token}@github.com/{github_username}/X403Agent.git"
            subprocess.run(
                ["git", "remote", "add", "origin", repo_url],
                cwd=temp_dir,
                check=True,
                capture_output=True,
                timeout=5
            )
            
            # Try main branch first, then master
            last_error = None
            for branch in ["main", "master"]:
                result = subprocess.run(
                    ["git", "push", "-u", "origin", branch, "--force"],
                    cwd=temp_dir,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    return {
                        "success": True,
                        "message": f"Pushed database to X403Agent (branch: {branch})"
                    }
                last_error = result.stderr
            
            return {
                "success": False,
                "message": f"Failed to push to both main and master branches: {last_error}"
            }
            
        finally:
            # Clean up
            shutil.rmtree(temp_dir, ignore_errors=True)
            
    except Exception as e:
        return {
            "success": False,
            "message": f"Error: {str(e)}"
        }

if __name__ == "__main__":
    result = push_database_to_x403agent()
    print(f"Success: {result['success']}")
    print(f"Message: {result['message']}")

