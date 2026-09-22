import ctypes
from ctypes import wintypes
import hashlib
import json
import pathlib
import queue
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

import frida

BASE = pathlib.Path(__file__).parent
EXPECTED_EXE = pathlib.Path(r"D:\MY.GAMES\Rush Royale PC\WinRR.exe")
GAME_ASSEMBLY = EXPECTED_EXE.parent / "GameAssembly.dll"
EXPECTED_SHA256 = "EF0D77A0660949397CAA287D951BDD86B39651797B5B36CEFDC2331DD6B9E425"
MAPPING_FILE = BASE / "card_mapping.json"
GUI_MUTEX_NAME = "Local\\MushRoyaleControlledSummonLab"
_gui_mutex = None

def acquire_single_instance():
    global _gui_mutex
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    ctypes.set_last_error(0)
    handle = kernel32.CreateMutexW(None, False, GUI_MUTEX_NAME)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == 183:
        kernel32.CloseHandle(handle)
        return False
    _gui_mutex = handle
    return True

def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()

def image_path(pid):
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = k32.OpenProcess(0x1000, False, pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        size = wintypes.DWORD(32768)
        buf = ctypes.create_unicode_buffer(size.value)
        if not k32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        return pathlib.Path(buf.value)
    finally:
        k32.CloseHandle(handle)

def find_pid():
    candidates = [p for p in frida.get_local_device().enumerate_processes()
                  if p.name.lower() == "winrr.exe"]
    exact = [p.pid for p in candidates if image_path(p.pid).resolve() == EXPECTED_EXE.resolve()]
    if len(exact) != 1:
        raise RuntimeError(f"Expected one Mush process at {EXPECTED_EXE}; found {len(exact)}")
    return exact[0]

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Mush Royale — Controlled Summon Lab")
        self.root.geometry("820x560")
        self.events = queue.Queue()
        self.session = self.script = self.api = None
        self.pending_slot = None
        self.calibrated_instance = None
        self.calibration_result = None
        self.collecting = False
        self.collection_count = 0
        self.known_names = {}
        self.cards = self.load_cards()
        self.status = tk.StringVar(value="Detached — start Mush Royale first")
        style = ttk.Style(root)
        style.configure("Action.TButton", font=("Segoe UI", 10, "bold"), padding=7)
        tk.Label(root, text="Mush Royale Summon Lab", font=("Segoe UI", 20, "bold"), fg="#28364a").pack(pady=(14, 4))
        tk.Label(root, textvariable=self.status, wraplength=610).pack(pady=(0, 12))
        controls = tk.Frame(root); controls.pack()
        ttk.Button(controls, text="1. Attach", style="Action.TButton", command=self.attach).grid(row=0, column=0, padx=5)
        ttk.Button(controls, text="2. Calibrate", style="Action.TButton", command=self.calibrate).grid(row=0, column=1, padx=5)
        ttk.Button(controls, text="3. Collect all 5", style="Action.TButton", command=self.start_collection).grid(row=0, column=2, padx=5)
        ttk.Button(controls, text="4. Discover merge", style="Action.TButton", command=self.discover_merge).grid(row=0, column=3, padx=5)
        ttk.Button(controls, text="STOP ALL", style="Action.TButton", command=self.stop_force).grid(row=0, column=4, padx=5)
        self.rows = []
        frame = tk.LabelFrame(root, text="Five-card deck mapping", padx=10, pady=8); frame.pack(fill="x", padx=18, pady=15)
        for i in range(5):
            name = tk.StringVar(); raw = tk.StringVar()
            tk.Label(frame, text=f"Card {i+1}", width=8, anchor="w").grid(row=i, column=0, pady=5)
            tk.Entry(frame, textvariable=name, width=22).grid(row=i, column=1, padx=4)
            tk.Entry(frame, textvariable=raw, width=15, state="readonly").grid(row=i, column=2, padx=4)
            ttk.Button(frame, text="Force summon", width=13, command=lambda n=i:self.force(n)).grid(row=i, column=3, padx=4)
            ttk.Button(frame, text="Force merge", width=13, command=lambda n=i:self.force_merge(n)).grid(row=i, column=4, padx=4)
            self.rows.append((name, raw))
        custom = tk.LabelFrame(root, text="Direct ID test (advanced)", padx=10, pady=7); custom.pack(fill="x", padx=18, pady=(0, 10))
        self.custom_id = tk.StringVar()
        tk.Label(custom, text="Raw 32-bit ID:").pack(side="left")
        tk.Entry(custom, textvariable=self.custom_id, width=18).pack(side="left", padx=8)
        ttk.Button(custom, text="FORCE CUSTOM ID", command=self.force_custom).pack(side="left")
        tk.Label(custom, text="Invalid IDs may be rejected by the game.", fg="#8a4b08").pack(side="left", padx=10)
        self.no_cost = tk.BooleanVar(value=False)
        mana = tk.LabelFrame(root, text="Mana / summon cost", padx=10, pady=7); mana.pack(fill="x", padx=18, pady=(0, 10))
        ttk.Checkbutton(mana, text="No summon cost (local player only)", variable=self.no_cost,
                        command=self.toggle_no_cost).pack(side="left")
        tk.Label(mana, text="Experimental: forces the verified cost getters to 0", fg="#5c6773").pack(side="left", padx=12)
        self.log = tk.Text(root, height=10, state="disabled", font=("Consolas", 9)); self.log.pack(fill="both", expand=True, padx=18, pady=(0, 14))
        self.refresh_rows(); self.root.after(100, self.poll); self.root.protocol("WM_DELETE_WINDOW", self.close)

    def load_cards(self):
        if MAPPING_FILE.exists():
            data = json.loads(MAPPING_FILE.read_text(encoding="utf-8"))
            if data.get("gameAssemblySha256") == EXPECTED_SHA256:
                cards, seen = [], set()
                for card in data.get("cards", []):
                    raw_id = card.get("id")
                    if raw_id is not None and raw_id in seen:
                        cards.append({"name":"", "id":None})
                    else:
                        cards.append(card)
                        if raw_id is not None: seen.add(raw_id)
                return cards
        return []
    def save_cards(self):
        cards = [{"name":n.get().strip(), "id":int(r.get()) if r.get() else None} for n,r in self.rows]
        MAPPING_FILE.write_text(json.dumps({"gameAssemblySha256":EXPECTED_SHA256,"cards":cards}, indent=2), encoding="utf-8")
    def refresh_rows(self):
        for i,(name,raw) in enumerate(self.rows):
            card = self.cards[i] if i < len(self.cards) else {}
            name.set(card.get("name", "")); raw.set("" if card.get("id") is None else str(card["id"]))
    def note(self, text):
        self.log.configure(state="normal"); self.log.insert("end", text+"\n"); self.log.see("end"); self.log.configure(state="disabled")
    def attach(self):
        if self.session is not None:
            return messagebox.showinfo("Already attached", "This window is already attached. Do not attach twice.")
        try:
            if digest(GAME_ASSEMBLY) != EXPECTED_SHA256: raise RuntimeError("GameAssembly hash mismatch")
            pid = find_pid(); self.session = frida.get_local_device().attach(pid)
            self.script = self.session.create_script((BASE/"forced_summon_lab.js").read_text(encoding="utf-8"))
            self.script.on("message", lambda m,d:self.events.put(m)); self.script.load(); self.api = self.script.exports_sync
            self.status.set(f"Attached safely to PID {pid}; observe-only")
        except Exception as exc: messagebox.showerror("Attach failed", str(exc))
    def calibrate(self):
        if not self.api: return messagebox.showwarning("Not attached", "Attach first.")
        result = self.api.armcalibration(); self.status.set("Armed: press Summon once. Existing AI instances are ignored."); self.note(str(result))
    def start_collection(self):
        if not self.api or not self.calibrated_instance:
            return messagebox.showwarning("Not calibrated", "Attach and calibrate your player first.")
        self.api.disable()
        self.known_names = {raw.get():name.get().strip() for name,raw in self.rows if raw.get()}
        for name,raw in self.rows:
            name.set(""); raw.set("")
        self.pending_slot = None
        self.collection_count = 0
        if self.calibration_result is not None:
            seed = str(self.calibration_result)
            self.rows[0][1].set(seed)
            self.rows[0][0].set(self.known_names.get(seed, ""))
            self.collection_count = 1
            self.note(f"Calibration summon included as first unique card: {seed}")
        self.collecting = True
        unique_count = sum(1 for _,raw in self.rows if raw.get())
        self.status.set(f"Collecting: {self.collection_count} pulls, {unique_count}/5 unique IDs. Continue until complete.")
        self.note("Collection started; forcing is disabled.")
    def learn(self, slot):
        if not self.api: return messagebox.showwarning("Not attached", "Attach and calibrate first.")
        try:
            self.api.armlearn(); self.pending_slot = slot
            self.status.set(f"Learning Card {slot+1}: press Summon once, then identify the visible unit.")
        except Exception as exc: messagebox.showerror("Cannot learn", str(exc))
    def force(self, slot):
        raw = self.rows[slot][1].get()
        if not self.api or not raw: return messagebox.showwarning("Unavailable", "Attach, calibrate, and learn this card first.")
        self.api.setforced(int(raw)); self.save_cards(); label = self.rows[slot][0].get() or f"Card {slot+1}"
        self.status.set(f"FORCING {label} ({raw}) for local-player summons only")
    def force_custom(self):
        if not self.api:
            return messagebox.showwarning("Not attached", "Attach and calibrate first.")
        try:
            raw = int(self.custom_id.get().strip(), 0)
            if raw < -2147483648 or raw > 4294967295: raise ValueError
            self.api.setforced(raw)
            self.status.set(f"FORCING custom ID {raw} for local-player summons only")
            self.note(f"Custom force enabled: {raw}")
        except ValueError:
            messagebox.showerror("Invalid ID", "Enter a decimal or 0x-prefixed 32-bit integer.")
    def toggle_no_cost(self):
        if not self.api:
            self.no_cost.set(False)
            return messagebox.showwarning("Not attached", "Attach and calibrate first.")
        try:
            result = self.api.setnocost(self.no_cost.get())
            state = "enabled" if result["noSummonCost"] else "disabled"
            self.status.set(f"No summon cost {state}")
            self.note(str(result))
        except Exception as exc:
            self.no_cost.set(False)
            messagebox.showerror("Cannot change summon cost", str(exc))
    def discover_merge(self):
        if not self.api or not self.calibrated_instance:
            return messagebox.showwarning("Not calibrated", "Attach and calibrate your player first.")
        try:
            result = self.api.startmergediscovery()
            self.status.set("Merge discovery active: perform three normal merges")
            self.note(str(result))
        except Exception as exc:
            messagebox.showerror("Merge discovery failed", str(exc))
    def force_merge(self, slot):
        raw = self.rows[slot][1].get()
        if not self.api or not raw:
            return messagebox.showwarning("Unavailable", "Attach, calibrate, collect cards, and discover merge first.")
        try:
            self.api.setmergeforced(int(raw)); self.save_cards()
            label = self.rows[slot][0].get() or f"Card {slot+1}"
            self.status.set(f"FORCING merge result {label} ({raw})")
        except Exception as exc:
            messagebox.showerror("Cannot force merge", str(exc))
    def stop_force(self):
        if self.api:
            self.api.disable(); self.api.disablemerge(); self.api.setnocost(False)
        self.no_cost.set(False)
        self.status.set("All forcing disabled; natural RNG restored")
    def poll(self):
        try:
            while True:
                msg = self.events.get_nowait(); payload = msg.get("payload", msg); self.note(json.dumps(payload))
                event = payload.get("event") if isinstance(payload, dict) else None
                if event == "calibrated":
                    self.calibrated_instance = payload["instance"]
                    self.calibration_result = payload["observedResult"]
                    mpp = payload.get("mpp")
                    self.status.set("Player + mana state calibrated" if mpp else "Player calibrated; mana state not linked")
                elif event == "observed" and self.collecting and payload.get("instance") == self.calibrated_instance:
                    self.collection_count += 1
                    learned_id = str(payload["result"])
                    existing = next((i for i,(_,raw) in enumerate(self.rows) if raw.get() == learned_id), None)
                    if existing is None:
                        empty = next((i for i,(_,raw) in enumerate(self.rows) if not raw.get()), None)
                        if empty is not None:
                            self.rows[empty][1].set(learned_id)
                            self.rows[empty][0].set(self.known_names.get(learned_id, ""))
                            self.note(f"New unique card: {learned_id} -> slot {empty+1}")
                    unique_count = sum(1 for _,raw in self.rows if raw.get())
                    if unique_count >= 5:
                        self.collecting = False
                        self.save_cards()
                        self.status.set(f"Complete after {self.collection_count} pulls: 5/5 IDs; add names and select FORCE")
                    else:
                        self.status.set(f"Collecting: {self.collection_count} pulls, {unique_count}/5 unique IDs")
                elif event == "learned" and self.pending_slot is not None:
                    slot = self.pending_slot
                    learned_id = str(payload["observedResult"])
                    duplicate_slot = next((i for i,(_,raw) in enumerate(self.rows)
                                           if i != slot and raw.get() == learned_id), None)
                    if duplicate_slot is not None:
                        duplicate_name = self.rows[duplicate_slot][0].get() or f"Card {duplicate_slot+1}"
                        self.note(f"Duplicate ignored: {learned_id} is already {duplicate_name}.")
                        self.status.set(f"Duplicate {duplicate_name}; summon again—still learning Card {slot+1}")
                        try:
                            self.api.armlearn()
                        except Exception as exc:
                            self.pending_slot = None
                            messagebox.showerror("Learning stopped", str(exc))
                        continue
                    self.pending_slot = None
                    self.rows[slot][1].set(learned_id)
                    name = simpledialog.askstring("Name this card", "Which card/unit appeared?", parent=self.root)
                    if name: self.rows[slot][0].set(name)
                    self.save_cards(); self.status.set(f"Card {slot+1} learned; forcing remains off")
                elif event == "forced": self.status.set(f"Forced {payload['forcedResult']} (replacement #{payload['replacements']})")
                elif event == "merge_candidate":
                    self.status.set(f"Merge candidate {payload['callerRva']}: {payload['count']}/3 confirmations")
                elif event == "merge_discovered":
                    self.status.set(f"Merge route found at {payload['callerRva']}; Force merge is available")
                elif event == "merge_forced":
                    self.status.set(f"Forced merge {payload['forcedResult']} (replacement #{payload['replacements']})")
                elif event == "cost_forced":
                    self.status.set(f"No-cost active: blocked {payload['method']} cost {payload['originalCost']}")
        except queue.Empty: pass
        self.root.after(100, self.poll)
    def close(self):
        try:
            self.save_cards()
            if self.api: self.api.disable(); self.api.disablemerge(); self.api.setnocost(False)
            if self.script: self.script.unload()
            if self.session: self.session.detach()
        finally: self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    if not acquire_single_instance():
        root.withdraw()
        messagebox.showerror("Already running", "Only one Mush Summon Lab window may run at a time.")
        root.destroy()
    else:
        App(root); root.mainloop()
