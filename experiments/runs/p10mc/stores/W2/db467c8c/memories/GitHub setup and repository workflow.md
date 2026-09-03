---
created: 2026-09-02T23:28:52.972842766Z
updated: 2026-09-02T23:28:52.972842766Z
weight: 1.0
last_accessed: 2026-09-02T23:28:52.972842766Z
access_count: 0
pinned: false
links: []
abstract: GitHub account setup, Git configuration, SSH key generation for SMC repository. Local clone, git add, commit, push workflow. SSH URLs preferred (git@github.com).
---

## GitHub Setup Steps for SMC

1. Create GitHub account at github.com/join
2. Install Git from git-scm.com/downloads

3. Configure Git globally:
   ```
   git config --global user.name "Your GitHub Username"
   git config --global user.email "youremail@example.com"
   ```

4. Generate SSH key (recommended over password auth):
   ```
   ssh-keygen -t ed25519 -C "youremail@example.com"
   eval "$(ssh-agent -s)"
   ssh-add ~/.ssh/id_ed25519
   ```
   Copy public key from ~/.ssh/id_ed25519.pub to GitHub Settings > SSH and GPG keys

5. Create new repository on GitHub (public/private choice)

6. Clone to local machine:
   ```
   git clone git@github.com:YourUsername/repository-name.git
   ```

7. Local workflow:
   ```
   git add .
   git commit -m "Initial commit"
   git push origin main
   ```

SSH URL format preferred: git@github.com:YourUsername/repo-name.git