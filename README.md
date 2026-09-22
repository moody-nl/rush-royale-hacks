# Rush Royale Hacks

A Frida-based modding tool for the **Windows Desktop version of Rush Royale (MY.GAMES)**.

**Tested and working very well in September 2026.**

## What It Does

### 🎯 Force Summon
1. Attach the tool to Rush Royale.
2. Calibrate by doing one normal summon.
3. Collect the 5 unique cards from your deck.
4. Select the card you want.
5. Enable **Force Summon**.
6. Your next summons are forced to the selected unit instead of the normal random result.

### 🔀 Force Merge
1. Click **Discover Merge**.
2. Perform 3 normal merges.
3. The tool identifies the merge process.
4. Select the unit you want.
5. Enable **Force Merge**.
6. Merge results are forced to the selected unit.

### 💧 No Summon Cost / Mana
1. Calibrate your player.
2. Enable **No Summon Cost**.
3. The detected summon cost is changed to **0**.

> ⚠️ **WARNING:** The mana/no-cost hack is experimental and potentially riskier than the summon and merge hacks. It works but don't do it in the begin of the game.

### 🛑 STOP ALL
Immediately disables:
- Force Summon
- Force Merge
- No Summon Cost

## Requirements

- Windows
- Rush Royale Desktop
- MY.GAMES Launcher
- Python 3
- Frida

```bash
pip install -r requirements.txt