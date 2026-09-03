---
created: 2026-09-03T01:32:20.464228991Z
updated: 2026-09-03T01:32:20.464228991Z
weight: 1.0
last_accessed: 2026-09-03T01:32:20.464228991Z
access_count: 0
pinned: false
links:
- dittobittys-equipable-weapons-system-design
abstract: Turn-based battle system for dittobitties with turn order by AGI, available actions (attack, defend, special ability, item), action effects calculation, victory/defeat conditions, and rewards system.
---

## Battle System Structure

### 1. Initiate Battle
- Retrieve dittobitties' stats and equipped weapons from database
- Determine turn order based on AGI or other factors

### 2. Turn-Based Battle Loop
```python
def battle(dittobitty1, dittobitty2):
    while True:
        # Dittobitty 1's turn
        action = choose_action(dittobitty1)
        perform_action(dittobitty1, dittobitty2, action)
        
        if is_defeated(dittobitty2):
            handle_victory(dittobitty1)
            break
        
        # Dittobitty 2's turn
        action = choose_action(dittobitty2)
        perform_action(dittobitty2, dittobitty1, action)
        
        if is_defeated(dittobitty1):
            handle_victory(dittobitty2)
            break
```

### Key Functions Needed:
- `choose_action(dittobitty)`: Determine available actions and choose one (AI, player input, or strategy-based)
- `perform_action(attacker, defender, action)`: Calculate and apply effects
  - Must incorporate dittobitty stats
  - Apply equipped weapon properties
  - Apply elemental damage effects
  - Apply action point costs
- `is_defeated(dittobitty)`: Check if health reaches 0
- `handle_victory(victorious_dittobitty)`: Award XP, currency, items, handle penalties for loser

### Available Actions Per Turn:
- Attack (using equipped weapon)
- Defend
- Use special ability
- Use item

### Damage Calculation Factors:
- Base weapon damage (varies by rarity and type)
- Dittobitty's attack stat
- Weapon elemental damage and effects
- Weapon bonus abilities (crits, deflects, stuns, etc.)
- Defender's defense stat
- Equipped defensive items/gear

### Victory Rewards:
- Experience points
- In-game currency
- Item drops
- Optional: penalties for defeated dittobitty