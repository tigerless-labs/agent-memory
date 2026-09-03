---
name: battle-system-architecture-turn-order-action-selection-damage-calculation-victor
abstract: "Battle system architecture: turn order, action selection, damage calculation, victory conditions"
type: procedure
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2026-09-02
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

Turn-based battle: (1) Initiate with dittobitties' stats and equipped weapons, determine turn order by AGI. (2) Battle loop cycles through: choose action (attack, defend, special ability, use item), calculate effects accounting for stats/weapons/effects, update health, check victory/defeat. (3) Handle outcome (award experience/currency/penalties). Key functions: battle(dittobitty1, dittobitty2), choose_action(), perform_action(attacker, defender, action), is_defeated(), handle_victory(). Expand perform_action to calculate damage using weapon properties and elemental effects.
