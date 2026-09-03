---
name: dittobitties-game-turn-based-battle-system-architecture-with-actions-effects-and
abstract: "Dittobitties game: turn-based battle system architecture with actions, effects, and victory conditions"
type: decision
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2023-05-21
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

## Battle System Design

### Battle Flow
1. Initiate battle between two dittobitties
2. Retrieve dittobitties' information from database (stats, equipped weapons)
3. Determine turn order (based on Agility or other factors)
4. Execute turn-based battle loop

### Turn-Based Loop
Each turn:
- Determine available actions for active dittobitty (attack, defend, special ability, items)
- Calculate action effects based on:
  - Dittobitty stats
  - Equipped weapon properties (damage, elemental type, bonus abilities)
  - Action point costs
- Update health and relevant stats after each action
- Check victory/defeat conditions

### Victory/Defeat Conditions
- Battle ends when one dittobitty is defeated (health reaches 0)
- Award outcomes to victor: experience points, in-game currency, other rewards
- Apply consequences to defeated dittobitty (optional)

### Function Components Needed
- choose_action(): Determine available actions based on dittobitty strategy or player input
- perform_action(): Calculate and apply action effects
- is_defeated(): Check if dittobitty health ≤ 0
- handle_victory(): Award rewards to victorious dittobitty
- Specific functions for each action/elemental effect
