"""Git publisher module for pushing database to GitHub"""
import subprocess
import os
import sys
from datetime import datetime

def check_git_repo(path="."):
    """Check if current directory is a git repository"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except:
        return False

def git_add_and_commit(db_path, repo_path=".."):
    """
    Add database file to git and commit it
    
    Args:
        db_path: Path to database file (relative to bot directory)
        repo_path: Path to git repository root (default: parent directory)
    
    Returns:
        dict with success status and message
    """
    try:
        # Get absolute paths
        bot_dir = os.path.dirname(os.path.abspath(__file__))
        abs_repo_path = os.path.abspath(os.path.join(bot_dir, repo_path))
        abs_db_path = os.path.abspath(os.path.join(bot_dir, db_path))
        
        # Check if git repo exists
        if not check_git_repo(abs_repo_path):
            return {
                "success": False,
                "message": "Not a git repository. Initialize with: git init"
            }
        
        # Check if database file exists
        if not os.path.exists(abs_db_path):
            return {
                "success": False,
                "message": f"Database file not found: {db_path}"
            }
        
        # Get relative path from repo root
        rel_db_path = os.path.relpath(abs_db_path, abs_repo_path)
        
        # Reset any other staged files first (only commit database)
        subprocess.run(
            ["git", "reset"],
            cwd=abs_repo_path,
            capture_output=True,
            timeout=5
        )
        
        # Add database file to git (force add even if in .gitignore)
        result = subprocess.run(
            ["git", "add", "-f", rel_db_path],
            cwd=abs_repo_path,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            return {
                "success": False,
                "message": f"Failed to add file: {result.stderr}"
            }
        
        # Check if there are changes to commit (only check the database file)
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet", rel_db_path],
            cwd=abs_repo_path,
            timeout=5
        )
        
        if result.returncode == 0:
            # No changes to commit
            return {
                "success": True,
                "message": "No changes to commit (database unchanged)"
            }
        
        # Verify only database file is staged
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=abs_repo_path,
            capture_output=True,
            text=True,
            timeout=5
        )
        
        staged_files = [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]
        if len(staged_files) > 1 or (staged_files and staged_files[0] != rel_db_path):
            # Unstage everything and re-add only database
            subprocess.run(
                ["git", "reset"],
                cwd=abs_repo_path,
                capture_output=True,
                timeout=5
            )
            subprocess.run(
                ["git", "add", "-f", rel_db_path],
                cwd=abs_repo_path,
                capture_output=True,
                timeout=5
            )
        
        # Check and configure git user config if not set
        user_name = subprocess.run(
            ["git", "config", "user.name"],
            cwd=abs_repo_path,
            capture_output=True,
            text=True,
            timeout=5
        )
        user_email = subprocess.run(
            ["git", "config", "user.email"],
            cwd=abs_repo_path,
            capture_output=True,
            text=True,
            timeout=5
        )
        
        # Auto-configure git user if not set
        if not user_name.stdout.strip():
            subprocess.run(
                ["git", "config", "user.name", "X403 Bot"],
                cwd=abs_repo_path,
                capture_output=True,
                timeout=5
            )
        
        if not user_email.stdout.strip():
            subprocess.run(
                ["git", "config", "user.email", "bot@x403.local"],
                cwd=abs_repo_path,
                capture_output=True,
                timeout=5
            )
        
        # Final check: ensure only database file is staged
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=abs_repo_path,
            capture_output=True,
            text=True,
            timeout=5
        )
        staged_files = [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]
        
        # Only proceed if exactly one file (the database) is staged
        if len(staged_files) != 1 or staged_files[0] != rel_db_path:
            # Force reset and re-add only database
            subprocess.run(["git", "reset"], cwd=abs_repo_path, capture_output=True, timeout=5)
            subprocess.run(["git", "add", "-f", rel_db_path], cwd=abs_repo_path, capture_output=True, timeout=5)
            # Verify again
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                cwd=abs_repo_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            staged_files = [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]
            if len(staged_files) != 1 or staged_files[0] != rel_db_path:
                return {
                    "success": False,
                    "message": f"Failed to stage only database file. Staged files: {staged_files}"
                }
        
        # Commit the changes (only the database file)
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        commit_message = f"Update token holders database - {timestamp}"
        
        result = subprocess.run(
            ["git", "commit", "-m", commit_message],
            cwd=abs_repo_path,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            error_msg = result.stderr.strip()
            if "Author identity unknown" in error_msg or "tell me who you are" in error_msg:
                return {
                    "success": False,
                    "message": "Git user identity not configured. Run: git config user.name 'Your Name' && git config user.email 'your@email.com'"
                }
            return {
                "success": False,
                "message": f"Failed to commit: {error_msg}"
            }
        
        return {
            "success": True,
            "message": f"Committed database update: {commit_message}"
        }
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "message": "Git operation timed out"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error: {str(e)}"
        }

def git_push(repo_path="..", branch="main", github_token=None, target_repo=None, github_username=None, db_path=None):
    """
    Push commits to GitHub
    
    Args:
        repo_path: Path to git repository root
        branch: Branch name to push (default: main)
        github_token: GitHub Personal Access Token for authentication
        target_repo: Target repository name (e.g., 'X403Agent')
        github_username: GitHub username (will be fetched from API if not provided)
    
    Returns:
        dict with success status and message
    """
    try:
        bot_dir = os.path.dirname(os.path.abspath(__file__))
        abs_repo_path = os.path.abspath(os.path.join(bot_dir, repo_path))
        
        # Check if git repo exists
        if not check_git_repo(abs_repo_path):
            return {
                "success": False,
                "message": "Not a git repository"
            }
        
        # If target_repo is specified, use it instead of current remote
        if target_repo and github_token:
            # Get username from GitHub API if not provided
            if not github_username:
                import requests
                headers = {
                    "Authorization": f"token {github_token}",
                    "Accept": "application/vnd.github.v3+json"
                }
                try:
                    user_response = requests.get("https://api.github.com/user", headers=headers, timeout=10)
                    if user_response.status_code == 200:
                        github_username = user_response.json()["login"]
                    else:
                        return {
                            "success": False,
                            "message": f"Failed to get GitHub username: {user_response.status_code}"
                        }
                except Exception as e:
                    return {
                        "success": False,
                        "message": f"Failed to get GitHub username: {str(e)}"
                    }
            
            # Set remote URL to target repository
            new_url = f"https://{github_token}@github.com/{github_username}/{target_repo}.git"
            subprocess.run(
                ["git", "remote", "set-url", "origin", new_url],
                cwd=abs_repo_path,
                capture_output=True,
                timeout=5
            )
            remote_url = new_url
            
            # For X403Agent repo, we want to push only the database file
            # Check if we need to create a separate branch or use --force-with-lease
            # But first, let's try pushing only the current commit
        else:
            # Check if remote is configured
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=abs_repo_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                return {
                    "success": False,
                    "message": "No remote 'origin' configured. Set with: git remote add origin <url>"
                }
            
            remote_url = result.stdout.strip()
            
            # If GitHub token is provided, use it for authentication
            if github_token:
                # Modify remote URL to include token if it's a GitHub HTTPS URL
                if "github.com" in remote_url and "https://" in remote_url:
                    # Extract repo path from URL
                    if "@" in remote_url:
                        # Already has credentials, replace them
                        repo_part = remote_url.split("@")[-1]
                    else:
                        # No credentials, extract repo path
                        repo_part = remote_url.replace("https://", "").replace("http://", "")
                        if "github.com/" in repo_part:
                            repo_part = repo_part.split("github.com/")[-1]
                    
                    # Set remote URL with token
                    new_url = f"https://{github_token}@github.com/{repo_part}"
                    subprocess.run(
                        ["git", "remote", "set-url", "origin", new_url],
                        cwd=abs_repo_path,
                        capture_output=True,
                        timeout=5
                    )
        
        # Push to GitHub
        env = os.environ.copy()
        if github_token:
            # Set token in environment for git credential helper
            env["GIT_ASKPASS"] = "echo"
            env["GIT_TERMINAL_PROMPT"] = "0"
        
        # Push to GitHub
        # For X403Agent, we need to push only the database file without workflow files
        # The issue is that git push tries to push all commits, including ones with workflow files
        # Solution: Use a separate branch or push only specific commits
        
        push_cmd = ["git", "push", "origin", f"{branch}"]
        
        # If target_repo is X403Agent, use a clean push method to avoid workflow file issues
        if target_repo == "X403Agent" and db_path:
            # Import the clean push function
            try:
                import sys
                bot_dir = os.path.dirname(os.path.abspath(__file__))
                if bot_dir not in sys.path:
                    sys.path.insert(0, bot_dir)
                
                from push_to_x403agent import push_file_to_x403agent
                
                # Get the absolute path to the file
                # file_path parameter should be relative to bot directory
                if os.path.isabs(db_path):
                    abs_file = db_path
                else:
                    abs_file = os.path.join(bot_dir, db_path)
                
                # Get relative path from bot directory
                file_rel = os.path.relpath(abs_file, bot_dir)
                
                # Determine file type
                file_type = "csv" if file_rel.endswith(".csv") else "database"
                
                # Use clean push method that creates a fresh repo with only the file
                # This avoids workflow file issues from the main repo's history
                push_result = push_file_to_x403agent(
                    file_path=file_rel,
                    github_token=github_token,
                    github_username=github_username,
                    file_type=file_type
                )
                return push_result
            except Exception as e:
                # Fallback to normal push if clean method fails
                print(f"   ⚠️  Clean push method failed: {e}, trying normal push...")
        
        # Normal push for other repositories or fallback
        result = subprocess.run(
            push_cmd,
            cwd=abs_repo_path,
            capture_output=True,
            text=True,
            timeout=30,
            env=env
        )
        
        if result.returncode != 0:
            error_msg = result.stderr.strip()
            
            # If it's a workflow scope issue, provide helpful message
            if "workflow" in error_msg.lower() and "scope" in error_msg.lower():
                return {
                    "success": False,
                    "message": "GitHub token needs 'workflow' scope to push workflow files. Either: 1) Add 'workflow' scope to your token, or 2) Remove .github/workflows files from X403Agent repository"
                }
            
            # Don't expose token in error messages
            if github_token and github_token in error_msg:
                error_msg = error_msg.replace(github_token, "***TOKEN***")
            return {
                "success": False,
                "message": f"Failed to push: {error_msg}"
            }
        
        return {
            "success": True,
            "message": f"Pushed to GitHub (branch: {branch})"
        }
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "message": "Push operation timed out"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error: {str(e)}"
        }

def git_add_and_commit_csv(csv_path, repo_path=".."):
    """
    Add and commit CSV file to git repository
    
    Args:
        csv_path: Path to CSV file (relative to bot directory)
        repo_path: Path to git repository root
        
    Returns:
        dict with success status and message
    """
    try:
        bot_dir = os.path.dirname(os.path.abspath(__file__))
        abs_repo_path = os.path.abspath(os.path.join(bot_dir, repo_path))
        
        # Get absolute path to CSV file
        if os.path.isabs(csv_path):
            abs_csv_path = csv_path
        else:
            abs_csv_path = os.path.join(bot_dir, csv_path)
        
        # Get relative path from repo root
        rel_csv_path = os.path.relpath(abs_csv_path, abs_repo_path)
        
        # Check if CSV file exists
        if not os.path.exists(abs_csv_path):
            return {
                "success": False,
                "message": f"CSV file not found: {abs_csv_path}"
            }
        
        # Reset any staged files
        subprocess.run(["git", "reset"], cwd=abs_repo_path, capture_output=True, timeout=5)
        
        # Add CSV file
        subprocess.run(
            ["git", "add", "-f", rel_csv_path],
            cwd=abs_repo_path,
            capture_output=True,
            timeout=5
        )
        
        # Configure git user if needed
        user_name = subprocess.run(
            ["git", "config", "user.name"],
            cwd=abs_repo_path,
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if not user_name.stdout.strip():
            subprocess.run(
                ["git", "config", "user.name", "X403 Bot"],
                cwd=abs_repo_path,
                capture_output=True,
                timeout=5
            )
        
        user_email = subprocess.run(
            ["git", "config", "user.email"],
            cwd=abs_repo_path,
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if not user_email.stdout.strip():
            subprocess.run(
                ["git", "config", "user.email", "bot@x403.local"],
                cwd=abs_repo_path,
                capture_output=True,
                timeout=5
            )
        
        # Check if there are changes
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=abs_repo_path,
            capture_output=True,
            text=True,
            timeout=5
        )
        
        staged_files = [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]
        
        if not staged_files:
            return {
                "success": True,
                "message": "No changes to commit (CSV unchanged)"
            }
        
        # Commit the CSV file
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        commit_message = f"Update token holders CSV - {timestamp}"
        
        result = subprocess.run(
            ["git", "commit", "-m", commit_message],
            cwd=abs_repo_path,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            error_msg = result.stderr.strip()
            if "nothing to commit" in error_msg.lower():
                return {
                    "success": True,
                    "message": "No changes to commit (CSV unchanged)"
                }
            return {
                "success": False,
                "message": f"Failed to commit: {error_msg}"
            }
        
        return {
            "success": True,
            "message": f"Committed CSV update: {commit_message}"
        }
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "message": "Git operation timed out"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error: {str(e)}"
        }

def publish_csv(csv_path="token_holders.csv", repo_path="..", branch="main", push=True, github_token=None, target_repo=None, github_username=None):
    """
    Publish CSV file to GitHub (commit and optionally push)
    
    Args:
        csv_path: Path to CSV file
        repo_path: Path to git repository root
        branch: Branch name
        push: Whether to push to remote (default: True)
        github_token: GitHub Personal Access Token for authentication
        target_repo: Target repository name (e.g., 'X403Agent')
        github_username: GitHub username (will be fetched from API if not provided)
    
    Returns:
        dict with success status and messages
    """
    result = {
        "commit": None,
        "push": None,
        "success": False
    }
    
    # Commit CSV
    commit_result = git_add_and_commit_csv(csv_path, repo_path)
    result["commit"] = commit_result
    
    if not commit_result["success"]:
        return result
    
    # Push to GitHub if requested
    if push and commit_result["message"] != "No changes to commit (CSV unchanged)":
        push_result = git_push(repo_path, branch, github_token, target_repo, github_username, csv_path)
        result["push"] = push_result
        result["success"] = push_result["success"]
    else:
        result["success"] = True
        if not push:
            result["push"] = {"success": True, "message": "Push skipped (push=False)"}
        else:
            result["push"] = {"success": True, "message": "No push needed (no changes)"}
    
    return result

def publish_database(db_path="token_holders.db", repo_path="..", branch="main", push=True, github_token=None, target_repo=None, github_username=None):
    """
    Publish database to GitHub (commit and optionally push)
    
    Args:
        db_path: Path to database file
        repo_path: Path to git repository root
        branch: Branch name
        push: Whether to push to remote (default: True)
        github_token: GitHub Personal Access Token for authentication
        target_repo: Target repository name (e.g., 'X403Agent')
        github_username: GitHub username (will be fetched from API if not provided)
    
    Returns:
        dict with success status and messages
    """
    result = {
        "commit": None,
        "push": None,
        "success": False
    }
    
    # Commit database
    commit_result = git_add_and_commit(db_path, repo_path)
    result["commit"] = commit_result
    
    if not commit_result["success"]:
        return result
    
    # Push to GitHub if requested
    if push and commit_result["message"] != "No changes to commit (database unchanged)":
        push_result = git_push(repo_path, branch, github_token, target_repo, github_username, db_path)
        result["push"] = push_result
        result["success"] = push_result["success"]
    else:
        result["success"] = True
        if not push:
            result["push"] = {"success": True, "message": "Push skipped (push=False)"}
        else:
            result["push"] = {"success": True, "message": "No push needed (no changes)"}
    
    return result

