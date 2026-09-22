# Mush Royale — Research Trajectory

## Objective

The project began as research into a **Rush Royale tactical/analysis tool** and gradually evolved into a full security and reverse-engineering analysis of the Windows client.

Final objective:

> Understand client behavior → demonstrate vulnerable trust assumptions → collect reproducible findings → enable detection/mitigation → report the results.

---

## 1. First Attempt — Computer Vision

The first prototypes attempted to reconstruct the game board from screenshots.

Research included:

- Board/grid detection
- Unit recognition
- Merge-rank recognition
- Hover inspector
- Tactical overlay/HUD

### Result

Board geometry worked reasonably well, but identifying units through colors and visual variation was not reliable enough.

**Conclusion:** Do not continue investing in heuristic computer vision as the primary data source.

---

## 2. Game Architecture Identified

The Windows installation was investigated.

Important files:

- `WinRR.exe`
- `UnityPlayer.dll`
- `GameAssembly.dll`
- `global-metadata.dat`

This established that:

> Rush Royale PC uses **Unity IL2CPP**.

This made static metadata analysis and runtime analysis possible.

---

## 3. IL2CPP Metadata Analysis

`global-metadata.dat` and `GameAssembly.dll` were analyzed.

Identified:

- Unity 6000.x
- IL2CPP metadata v31.x
- ~41k TypeDefinitions
- ~267k methods
- HybridCLR present

Interesting assemblies included:

- `Random.GameModel.dll`
- `Random.dll`
- `Core.Replays.dll`
- `Core.Cheats.dll`

Gameplay-related concepts also became visible, including:

- Pawn
- PawnState
- PlayerBoard
- Slot
- Merge
- Spawn
- Mana
- Wave/Boss
- Deck
- Effects

---

## 4. Cpp2IL Recovery

Because older IL2CPP tooling had problems processing metadata v31, **Cpp2IL** was used.

This reconstructed:

- Dummy DLLs
- IL-recovery assemblies
- Type information
- Fields
- Methods
- Source paths

This provided a much clearer view of the internal gameplay architecture.

---

## 5. LocalLow Telemetry

Local game files were investigated.

### `settings.json`

Contained information such as:

- Deck
- Pawn IDs
- Card levels
- Ascension/talents
- Hero
- Equipment

### `LogsStorage.json`

Contained information such as:

- `fightId`
- Game mode

This made it possible to detect match start and match end.

### `LocalStats.json`

Contained counters such as:

- Mana gain/use
- Merge count
- Spawn count
- Power-up count

---

## 6. Intelligence Mapper

The Cpp2IL output was indexed into a SQLite database:

`rush_typegraph.db`

The database contained:

- Assemblies
- Types
- Fields
- Methods
- Type relationships

Later versions added:

- Chain Hunt
- Object Graph
- Anchor Map
- Economy Map
- Reward Flow
- Trust Review

This made it possible to investigate the obfuscated code as a graph instead of manually searching through hundreds of DLLs.

---

## 7. Gameplay Object Graph Reconstruction

The mapper revealed relationships including:

`BoardSlotController → gameplay containers → PawnState`

A recurring structure appeared around:

`GBK → GBR → LSG → PawnState`

The exact meaning of the intermediate obfuscated types had not yet been fully proven, but the structure provided concrete runtime anchors.

---

## 8. Read-Only Live State Probe

Runtime research was added next.

The probe used:

- Process attachment
- Module enumeration
- `ReadProcessMemory`
- Memory snapshots
- Action labels
- LocalLow telemetry

No game-state writes were required during this phase.

Events were manually labeled as:

- Summon
- Merge
- Power-up
- Other

---

## 9. Precision Correlation

The initial memory scans produced too much noise.

Filtering was therefore introduced for:

- Stable chunks
- Noisy chunks
- Action correlation
- Control events
- Candidate ranking

This produced memory locations that strongly correlated with specific gameplay actions.

An important lesson was:

> A memory value that correlates perfectly with a Merge event is not necessarily actual gameplay Merge state.

Some strong candidates turned out to be related to graphics or UI state instead.

---

## 10. Runtime Object Tracing

The next step attempted to establish:

`correlated field → object → parent references → IL2CPP type`

Initial object detection produced false positives pointing into system and graphics modules.

The resolver was therefore progressively made more restrictive.

---

## 11. MetadataRegistration Discovery

A major breakthrough was reliably locating the live IL2CPP:

`MetadataRegistration`

This confirmed runtime counts for:

- Types
- TypeDefinitions
- Field offsets
- Generic classes
- Method specifications

This created a bridge between static metadata and the running game.

---

## 12. Metadata Parser Repair

An earlier resolver failed to locate target types because the metadata header had been interpreted incorrectly.

The following structures were then correctly identified:

- String table
- TypeDefinition table
- Record size
- TypeDefinition count

Concrete types could subsequently be located directly, including:

- `PawnState`
- `BoardSlotController`
- Multiple `Slot` types

This established the resolution path:

`metadata → TypeDefinition → TypeIndex → runtime Il2CppType → Il2CppClass → instance`

---

## 13. Patch/Build Robustness

A distinction was established between:

- PID
- Module base
- Heap address
- RVA
- Pointer chain
- Metadata type
- Build hash

Important conclusions:

- PIDs change after restart.
- ASLR changes module base addresses.
- Heap addresses are temporary.
- RVAs are build-specific.
- Game updates may change metadata, layouts, and RVAs.

The desired update workflow therefore became:

`old build → new build → Cpp2IL → new DB → diff → remap → runtime validation`

---

## 14. Offensive Lab / Controlled PoC Phase

A separate research environment was then used to determine which client-side state could influence gameplay.

Research included:

- Runtime method resolution
- Summon tracing
- Callsite analysis
- Mana tracing
- Build hashes
- Calibration
- Captures

The PoC was deliberately tied to a specific `GameAssembly` hash so that an unknown/new build would not automatically be treated as if its previous offsets were still valid.

---

## 15. Primary Security Finding

The research demonstrated that certain gameplay outcomes could be influenced sufficiently from the client side to investigate relevant trust boundaries.

Within the test environment, research ultimately covered categories involving:

- Summon outcome
- Merge/game state
- Mana/resource state

This marked the point where the project moved beyond reverse engineering and produced an actual **security finding**.

---

## 16. From Exploit to Defense

The main conclusion was that detection should not simply ask:

`"Has memory address X been modified?"`

That approach is too build-specific.

A stronger model is:

`client action`
→ `server-authoritative expected state`
→ `observed state`
→ `invariant validation`
→ `anomaly`

Examples include:

- Valid resource transitions
- Valid summon transitions
- Valid merge transitions
- Action-rate limits
- State-machine validation
- Server-side RNG/authority where required

---

## 17. Final Result

The project ultimately progressed through:

`CV prototype`
→ `Unity/IL2CPP identification`
→ `metadata extraction`
→ `Cpp2IL recovery`
→ `SQLite TypeGraph`
→ `object graph reconstruction`
→ `read-only runtime scanning`
→ `action correlation`
→ `metadata/runtime bridge`
→ `method/callsite tracing`
→ `controlled PoC`
→ `trust-boundary finding`
→ `detection/mitigation`
→ `patch/report`