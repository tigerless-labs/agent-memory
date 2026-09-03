---
name: github-setup-for-smc-ssh-key-repository-creation-commit-workflow
abstract: "GitHub setup for SMC - SSH key, repository creation, commit workflow"
type: procedure
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2023-07-11
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

GitHub setup procedure for SMC: Git configured globally with user.name and user.email (ruihanlee1030@gmail.com). SSH key generated (ed25519 recommended via ssh-keygen -t ed25519) for passwordless authentication. Public SSH key (.ssh/id_ed25519.pub) added to GitHub account settings under SSH and GPG keys. Repository created on GitHub, cloned to local machine using git clone with SSH URL (git@github.com:Username/repo-name.git). Files staged with git add, committed with meaningful messages, pushed to main branch with git push origin main.
