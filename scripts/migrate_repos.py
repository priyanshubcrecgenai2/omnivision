#!/usr/bin/env python3
import urllib.request
import json
import subprocess
import os
import shutil
import time

TOKEN = os.environ.get('GITHUB_TOKEN', '')
SOURCE_USER = 'priyanshu596'
TARGET_USER = 'priyanshubcrecgenai2'
TMP_DIR = '/tmp/repo_mirror_batch.git'

# Fetch target repos
req = urllib.request.Request(f'https://api.github.com/users/{TARGET_USER}/repos?per_page=100')
with urllib.request.urlopen(req) as resp:
    target_repos = {r['name'] for r in json.loads(resp.read().decode())}

print(f'Already in target ({len(target_repos)}): {sorted(list(target_repos))}')

# Fetch source repos
req_src = urllib.request.Request(f'https://api.github.com/users/{SOURCE_USER}/repos?per_page=100')
with urllib.request.urlopen(req_src) as resp:
    source_repos = json.loads(resp.read().decode())

to_copy = [
    r for r in source_repos
    if not r['fork']
    and r['name'] != SOURCE_USER
    and r['name'] not in target_repos
]

names_to_copy = [r['name'] for r in to_copy]
print(f'Remaining to copy ({len(to_copy)}): {names_to_copy}')

for idx, repo in enumerate(to_copy, 1):
    name = repo['name']
    desc = repo.get('description') or ''
    print(f'\n[{idx}/{len(to_copy)}] Processing {name}...')
    
    # Create target repo
    create_payload = json.dumps({'name': name, 'private': False, 'description': desc}).encode('utf-8')
    create_req = urllib.request.Request(
        'https://api.github.com/user/repos',
        data=create_payload,
        headers={
            'Authorization': f'token {TOKEN}',
            'Accept': 'application/vnd.github+json',
            'Content-Type': 'application/json'
        },
        method='POST'
    )
    
    created = False
    retries = 3
    while retries > 0 and not created:
        try:
            with urllib.request.urlopen(create_req) as resp:
                created = True
                print(f'   Repository {name} created on GitHub.')
        except urllib.error.HTTPError as e:
            if e.code == 403:
                print(f'   Hit rate limit (403), waiting 60s before retry...')
                time.sleep(60)
                retries -= 1
            elif e.code == 422:
                # Already exists
                print(f'   Repository {name} already exists (422).')
                created = True
            else:
                print(f'   HTTP error: {e.code}')
                break
                
    if not created:
        print(f'   Skipping {name} due to create errors.')
        continue
        
    # Bare clone and mirror push
    if os.path.exists(TMP_DIR):
        shutil.rmtree(TMP_DIR)
        
    src_url = f'https://github.com/{SOURCE_USER}/{name}.git'
    target_url = f'https://{TARGET_USER}:{TOKEN}@github.com/{TARGET_USER}/{name}.git'
    
    try:
        subprocess.run(['git', 'clone', '--bare', src_url, TMP_DIR], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['git', '-C', TMP_DIR, 'push', '--mirror', target_url], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f'   ✓ Pushed mirror for {name}.')
    except subprocess.CalledProcessError as e:
        print(f'   ✗ Error pushing {name}: {e}')
    finally:
        if os.path.exists(TMP_DIR):
            shutil.rmtree(TMP_DIR)
            
    # Sleep 8 seconds between repo creations to avoid triggering secondary rate limit
    time.sleep(8)

print('\nFinished batch migration!')
