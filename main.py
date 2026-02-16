#!/usr/bin/env python3
"""
Script to download OpenAPI spec, compare with existing, and commit changes if different.
Uses GitPython for Git operations and structured logging.
"""

import json
import logging
import os
import sys
import requests
from git import Repo, InvalidGitRepositoryError, GitCommandError


# Setup logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter(
    fmt='%(asctime)s %(name)12s: %(levelname)8s > %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
handler_console = logging.StreamHandler()
handler_console.setFormatter(formatter)
logger.addHandler(handler_console)


def download_file(url, timeout=30):
    """
    Download file from URL and return the content.

    Args:
        url: URL to download from
        timeout: Request timeout in seconds

    Returns:
        dict: Parsed JSON content, or None if failed
    """
    try:
        logger.info(f"Downloading from {url}")
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()

        # Parse JSON to ensure it's valid
        data = response.json()
        logger.info("Successfully downloaded and parsed JSON")
        return data

    except requests.RequestException as e:
        logger.error(f"Error downloading file: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return None


def save_file(content, filename):
    """
    Save content to a file.

    Args:
        content: String content to save
        filename: Output filename

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info(f"Saving to {filename}")
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"Successfully saved to {filename}")
        return True

    except Exception as e:
        logger.error(f"Error saving file: {e}")
        return False


def git_diff(filename):
    """
    Check if file has changes compared to git repository.

    Args:
        filename: File to check for changes

    Returns:
        bool: True if changes exist, False otherwise
    """
    try:
        repo = Repo('.')

        # Check if file is untracked
        if filename in repo.untracked_files:
            logger.info(f"File {filename} is untracked (new file)")
            return True

        # Check for staged changes
        diff_staged = repo.index.diff('HEAD')
        has_staged = any(item.a_path == filename for item in diff_staged)

        # Check for unstaged changes
        diff_unstaged = repo.index.diff(None)
        has_unstaged = any(item.a_path == filename for item in diff_unstaged)

        if has_staged or has_unstaged:
            logger.info(f"Changes detected in {filename}")
            return True

        # Double-check using git diff command
        try:
            diff_output = repo.git.diff('HEAD', filename)
            if diff_output:
                logger.info(f"Changes detected in {filename}")
                return True
        except GitCommandError:
            pass

        logger.info(f"No changes in {filename}")
        return False

    except InvalidGitRepositoryError:
        logger.error("Not in a git repository")
        return False
    except Exception as e:
        logger.error(f"Error checking git diff: {e}")
        return False


def git_commit(filename, message="Update openapi spec"):
    """
    Add and commit file(s) to git repository.

    Args:
        filename: File or list of files to commit
        message: Commit message

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        repo = Repo('.')

        # Normalize to list
        files = filename if isinstance(filename, list) else [filename]

        # Add file(s) to staging
        logger.info(f"Adding {files} to git staging")
        repo.index.add(files)

        # Commit changes
        logger.info(f"Committing with message: '{message}'")
        commit = repo.index.commit(message)
        logger.info(f"Successfully committed (hash: {commit.hexsha[:8]})")
        return True

    except InvalidGitRepositoryError:
        logger.error("Not in a git repository")
        return False
    except GitCommandError as e:
        logger.error(f"Git commit failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Error during commit: {e}")
        return False

def git_push():
    """Push commits to remote repository using SSH."""
    try:
        repo = Repo('.')

        if not repo.remotes:
            logger.error("No remote repository configured")
            return False

        branch = repo.active_branch.name
        origin = repo.remotes.origin if 'origin' in [r.name for r in repo.remotes] else repo.remotes[0]

        logger.info(f"Pushing to {origin.name}/{branch}")
        push_info = origin.push(branch)[0]

        if push_info.flags & push_info.ERROR:
            logger.error(f"Push failed: {push_info.summary}")
            return False
        elif push_info.flags & push_info.REJECTED:
            logger.error(f"Push rejected: {push_info.summary}")
            logger.info("Try: git pull --rebase")
            return False
        else:
            logger.info(f"Successfully pushed to {origin.name}/{branch}")
            return True

    except Exception as e:
        logger.error(f"Error during push: {e}")
        return False


def reorder_openapi_paths(file_path, output_path):
    # Load the JSON data
    with open(file_path, 'r') as f:
        data = json.load(f)

    if 'paths' in data:
        original_paths = data['paths']
        new_paths = {}

        # 1. Check if /token exists and add it first
        if '/token' in original_paths:
            new_paths['/token'] = original_paths['/token']

        # 2. Add all other paths in their original order
        for path, details in original_paths.items():
            if path != '/token':
                new_paths[path] = details

        # Replace the old paths object with the reordered one
        data['paths'] = new_paths

    # Modify securitySchemes
    if 'components' in data and 'securitySchemes' in data['components']:
        schemes = data['components']['securitySchemes']
        if 'GetToken' in schemes:
            # 1. change ApiKey.description to GetToken.description
            # GetToken is the same as ApiKey
            if 'ApiKey' in schemes and 'description' in schemes['GetToken']:
                schemes['ApiKey']['description'] = schemes['GetToken']['description']

            # 2. remove GetToken
            del schemes['GetToken']

            # 3. change GetToken to ApiKey in ALL endpoints
            # Doublechecking
            if 'paths' in data:
                for path, operations in data['paths'].items():
                    for method, details in operations.items():
                        if isinstance(details, dict):
                            if 'security' in details:
                                for scheme in details['security']:
                                    if 'GetToken' in scheme:
                                        print("!!! GetToken in {} {} !!!".format(method, path))
                                        scheme['ApiKey'] = scheme.pop('GetToken')

                            # 4. Add ApiToken to all endpoints so global config is not used
                            else:
                                details['security'] = [{"ApiToken": []}]

                            # 5. Change DenyList tag to Deny List
                            if 'tags' in details:
                                details['tags'] = ['Deny List' if tag == 'DenyList' else tag for tag in details['tags']]

    # Save the modified JSON
    with open(output_path + '.json', 'w') as f:
        json.dump(data, f, indent=2)

    with open(output_path + '_compressed.json', 'w') as f:
        json.dump(data, f)

    print(f"Successfully reordered paths. Output saved to: {output_path}")


def main():
    """
    Main function to orchestrate the download, save, diff, commit, and push process.
    """
    # Configuration
    API_URL = os.environ.get('VERKADA_OPENAPI_SPEC_URL')
    OUTPUT_FILE = "openapi.json"
    TRANSFORMED_OUTPUT = "openapi_transformed"

    # Optional: GitHub credentials (can use environment variables)
    GITHUB_USERNAME = os.environ.get('GITHUB_USERNAME')  # Optional
    GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')  # Optional - Personal Access Token

    logger.info("=== OpenAPI Specification Update Script ===")

    if not API_URL:
        logger.error("VERKADA_OPENAPI_SPEC_URL environment variable is not set. Exiting.")
        return 1

    # Step 1: Download file
    data = download_file(API_URL)
    if data is None:
        logger.error("Failed to download file. Exiting.")
        return 1

    # Step 2: Format JSON and save file
    formatted_json = json.dumps(data, indent=4, sort_keys=True, ensure_ascii=False)
    if not save_file(formatted_json, OUTPUT_FILE):
        logger.error("Failed to save file. Exiting.")
        return 1

    # Step 3: Check git diff
    has_changes = git_diff(OUTPUT_FILE)

    # Step 4: If changes exist, transform, commit, and push
    if has_changes:
        logger.info("Changes detected, proceeding with transform, commit, and push")

        # Step 4a: Commit the raw openapi spec
        if not git_commit(OUTPUT_FILE):
            logger.error("Failed to commit changes. Exiting.")
            return 1

        if not git_push():
            logger.error("Failed to push changes. Exiting.")
            return 1

        # Step 4b: Reorder and transform the openapi spec
        logger.info("Reordering and transforming OpenAPI spec")
        reorder_openapi_paths(OUTPUT_FILE, TRANSFORMED_OUTPUT)

        # Step 4c: Commit and push the transformed spec
        transformed_files = [
            TRANSFORMED_OUTPUT + '.json',
            TRANSFORMED_OUTPUT + '_compressed.json'
        ]

        if not git_commit(transformed_files, message="Update transformed openapi spec"):
            logger.error("Failed to commit transformed spec. Exiting.")
            return 1

        if not git_push():
            logger.error("Failed to push transformed spec. Exiting.")
            return 1

        logger.info("All operations completed successfully!")
    else:
        logger.info("No changes detected. Nothing to commit.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
