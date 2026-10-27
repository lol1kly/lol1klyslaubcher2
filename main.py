import json
import os
import re
import sys
import threading
import urllib.parse
import urllib.request
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

APP_NAME = "BlockLaunch"
ROOT = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / APP_NAME
VERSIONS_DIR = ROOT / "versions"
PROFILES_DIR = ROOT / "profiles"
JAVA_DIR = ROOT / "runtime"
CONFIG = ROOT / "config.json"
MODRINTH_API = "https://api.modrinth.com/v2"

def open_url(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "BlockLaunch/0.1 (launcher)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def get_json(url):
    return json.loads(open_url(url).decode("utf-8"))

def major_for_version(version):
    # Minecraft <=1.16.5 typically uses Java 8; 1.17 uses 16; 1.18+ uses 17;
    # newer releases may require 21. This is a practical default, not a universal rule.
    m = re.match(r"1\.(\d+)", version)
    if not m: return 21
    minor = int(m.group(1))
    if minor <= 16: return 8
    if minor == 17: return 16
    if minor <= 20: return 17
    return 21

def ensure_dirs():
    for p in (ROOT, VERSIONS_DIR, PROFILES_DIR, JAVA_DIR):
        p.mkdir(parents=True, exist_ok=True)

def safe_name(s):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("._") or "Profile"

class Launcher(tk.Tk):
    def __init__(self):
        super().__init__()
        ensure_dirs()
        self.title("BlockLaunch")
        self.geometry("920x660")
        self.minsize(780, 560)
        self.config_data = self.load_config()
        self.versions = []
        self.mod_results = []
        self.status = tk.StringVar(value="Готово")
        self._build_ui()
        self.log("BlockLaunch запущен. Версии загружаются из официального манифеста.")
        threading.Thread(target=self.refresh_versions, daemon=True).start()

    def load_config(self):
        try:
            return json.loads(CONFIG.read_text(encoding="utf-8"))
        except Exception:
            return {"nickname": "Player", "version": "", "profile": "Default", "memory": 4096}

    def save_config(self):
        self.config_data["nickname"] = self.nickname.get().strip() or "Player"
        self.config_data["version"] = self.version.get()
        self.config_data["profile"] = self.profile.get().strip() or "Default"
        try: self.config_data["memory"] = int(self.memory.get())
        except Exception: self.config_data["memory"] = 4096
        CONFIG.write_text(json.dumps(self.config_data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _build_ui(self):
        style = ttk.Style(self)
        try: style.theme_use("clam")
        except Exception: pass
        header = ttk.Frame(self, padding=12)
        header.pack(fill="x")
        ttk.Label(header, text="BLOCKLAUNCH", font=("Segoe UI", 20, "bold")).pack(side="left")
        ttk.Label(header, text="Minecraft • версии • Java • Modrinth", font=("Segoe UI", 10)).pack(side="left", padx=16)

        tabs = ttk.Notebook(self)
        tabs.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        self.play_tab = ttk.Frame(tabs, padding=14)
        self.mods_tab = ttk.Frame(tabs, padding=14)
        self.library_tab = ttk.Frame(tabs, padding=14)
        tabs.add(self.play_tab, text="Играть")
        tabs.add(self.library_tab, text="Версии и Java")
        tabs.add(self.mods_tab, text="Modrinth")

        ttk.Label(self.play_tab, text="Офлайн-профиль", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 10))
        ttk.Label(self.play_tab, text="Ник:").grid(row=1, column=0, sticky="w")
        self.nickname = tk.StringVar(value=self.config_data.get("nickname", "Player"))
        ttk.Entry(self.play_tab, textvariable=self.nickname, width=30).grid(row=1, column=1, sticky="w", padx=8)
        ttk.Label(self.play_tab, text="Версия Minecraft:").grid(row=2, column=0, sticky="w", pady=8)
        self.version = tk.StringVar(value=self.config_data.get("version", ""))
        self.version_combo = ttk.Combobox(self.play_tab, textvariable=self.version, width=28, state="readonly")
        self.version_combo.grid(row=2, column=1, sticky="w", padx=8)
        ttk.Label(self.play_tab, text="Профиль/папка:").grid(row=3, column=0, sticky="w")
        self.profile = tk.StringVar(value=self.config_data.get("profile", "Default"))
        ttk.Entry(self.play_tab, textvariable=self.profile, width=30).grid(row=3, column=1, sticky="w", padx=8)
        ttk.Label(self.play_tab, text="RAM (МБ):").grid(row=4, column=0, sticky="w", pady=8)
        self.memory = tk.StringVar(value=str(self.config_data.get("memory", 4096)))
        ttk.Entry(self.play_tab, textvariable=self.memory, width=10).grid(row=4, column=1, sticky="w", padx=8)
        ttk.Button(self.play_tab, text="Установить версию", command=self.install_version).grid(row=5, column=0, sticky="w", pady=10)
        ttk.Button(self.play_tab, text="Скачать Java и запустить", command=self.launch_game).grid(row=5, column=1, sticky="w", padx=8)
        ttk.Label(self.play_tab, text="Офлайн-режим не авторизует тебя в Microsoft и не даёт доступ к серверам с online-mode.", wraplength=700).grid(row=6, column=0, columnspan=3, sticky="w", pady=8)
        self.logbox = tk.Text(self.play_tab, height=13, wrap="word", state="disabled", bg="#111827", fg="#d1fae5", insertbackground="white")
        self.logbox.grid(row=7, column=0, columnspan=3, sticky="nsew", pady=(10, 0))
        self.play_tab.columnconfigure(2, weight=1)
        self.play_tab.rowconfigure(7, weight=1)

        ttk.Label(self.library_tab, text="Каталог данных лаунчера", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        ttk.Label(self.library_tab, text=str(ROOT), wraplength=820).pack(anchor="w", pady=5)
        ttk.Label(self.library_tab, text="Каждый профиль хранит данные отдельно; версии Minecraft устанавливаются в управляемый каталог.", wraplength=800).pack(anchor="w", pady=5)
        ttk.Button(self.library_tab, text="Обновить список версий", command=lambda: threading.Thread(target=self.refresh_versions, daemon=True).start()).pack(anchor="w", pady=8)
        self.version_list = tk.Listbox(self.library_tab, height=18)
        self.version_list.pack(fill="both", expand=True, pady=8)

        searchrow = ttk.Frame(self.mods_tab)
        searchrow.pack(fill="x")
        ttk.Label(searchrow, text="Мод на Modrinth:").pack(side="left")
        self.mod_query = tk.StringVar()
        ttk.Entry(searchrow, textvariable=self.mod_query).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(searchrow, text="Найти", command=self.search_mods).pack(side="left")
        ttk.Label(self.mods_tab, text="Выбери результат и скачай файл в папку mods выбранного профиля. Проверь совместимость версии и загрузчика.", wraplength=820).pack(anchor="w", pady=8)
        self.mod_list = tk.Listbox(self.mods_tab, height=18)
        self.mod_list.pack(fill="both", expand=True)
        ttk.Button(self.mods_tab, text="Скачать выбранный мод", command=self.download_mod).pack(anchor="w", pady=10)

        footer = ttk.Frame(self, padding=(12, 0, 12, 10))
        footer.pack(fill="x")
        ttk.Label(footer, textvariable=self.status).pack(side="left")

    def log(self, message):
        def append():
            self.logbox.configure(state="normal")
            self.logbox.insert("end", message + "\n")
            self.logbox.see("end")
            self.logbox.configure(state="disabled")
            self.status.set(message[:120])
        self.after(0, append)

    def refresh_versions(self):
        try:
            import minecraft_launcher_lib as mll
            all_versions = mll.utils.get_version_list()
            self.versions = all_versions
            # Latest first while keeping snapshots available.
            names = [v["id"] for v in all_versions]
            self.after(0, lambda: self.version_combo.configure(values=names))
            self.after(0, lambda: self.version_list.delete(0, "end"))
            for v in all_versions[:500]:
                self.after(0, lambda x=v: self.version_list.insert("end", f'{x["id"]}  [{x.get("type","?")}]'))
            latest = next((v["id"] for v in all_versions if v.get("type") == "release"), names[0] if names else "")
            if not self.version.get() and latest:
                self.after(0, lambda: self.version.set(latest))
            self.log(f"Список версий загружен: {len(all_versions)}")
        except Exception as e:
            self.log(f"Не удалось загрузить список версий: {e}")

    def install_version(self):
        version = self.version.get().strip()
        if not version:
            messagebox.showwarning("BlockLaunch", "Сначала выбери версию.")
            return
        self.save_config()
        self.log(f"Установка Minecraft {version}…")
        def worker():
            try:
                import minecraft_launcher_lib as mll
                path = str(VERSIONS_DIR)
                callback = {"setStatus": lambda s: self.log(str(s)), "setProgress": lambda p: None, "setMax": lambda m: None}
                mll.install.install_minecraft_version(version, path, callback=callback)
                self.log(f"Версия {version} установлена в {path}")
            except Exception as e:
                self.log(f"Ошибка установки: {e}")
        threading.Thread(target=worker, daemon=True).start()

    def profile_dir(self):
        return PROFILES_DIR / safe_name(self.profile.get().strip() or "Default")

    def ensure_java(self, major):
        java_home = JAVA_DIR / f"java-{major}"
        java_bin = java_home / ("bin/java.exe" if os.name == "nt" else "bin/java")
        if java_bin.exists():
            return str(java_bin)
        self.log(f"Скачиваю Java {major}…")
        # Adoptium returns a binary archive. Install into app-managed runtime folder.
        url = f"https://api.adoptium.net/v3/binary/latest/{major}/ga/windows/x64/jre/hotspot/normal/eclipse"
        if os.name != "nt":
            url = f"https://api.adoptium.net/v3/binary/latest/{major}/ga/linux/x64/jre/hotspot/normal/eclipse"
        archive = JAVA_DIR / f"java-{major}.zip"
        archive.write_bytes(open_url(url, timeout=120))
        import zipfile
        temp = JAVA_DIR / f"extract-{major}"
        temp.mkdir(exist_ok=True)
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(temp)
        roots = list(temp.iterdir())
        if not roots:
            raise RuntimeError("Архив Java пустой")
        if java_home.exists():
            import shutil; shutil.rmtree(java_home)
        roots[0].rename(java_home)
        import shutil; shutil.rmtree(temp, ignore_errors=True)
        archive.unlink(missing_ok=True)
        if not java_bin.exists():
            # Some JRE distributions have a nested directory layout.
            found = list(java_home.rglob("java.exe" if os.name == "nt" else "java"))
            if found: return str(found[0])
            raise RuntimeError("Не найден исполняемый файл Java после распаковки")
        return str(java_bin)

    def launch_game(self):
        version = self.version.get().strip()
        nick = self.nickname.get().strip()
        if not version or not nick:
            messagebox.showwarning("BlockLaunch", "Укажи ник и версию.")
            return
        self.save_config()
        self.log(f"Подготовка запуска {version} для {nick}…")
        def worker():
            try:
                import minecraft_launcher_lib as mll
                version_dir = VERSIONS_DIR / version
                if not version_dir.exists():
                    self.log("Версия ещё не установлена — сначала нажми «Установить версию».")
                    return
                java = self.ensure_java(major_for_version(version))
                game_dir = self.profile_dir()
                game_dir.mkdir(parents=True, exist_ok=True)
                options = {
                    "username": nick,
                    "uuid": "00000000-0000-0000-0000-" + (re.sub(r"[^a-fA-F0-9]", "", nick.lower()).ljust(12, "0")[:12]),
                    "token": "",
                    "executablePath": java,
                    "gameDirectory": str(game_dir),
                    "jvmArguments": [f"-Xmx{max(1024, int(self.memory.get()))}M", "-Xms512M"],
                }
                command = mll.command.get_minecraft_command(version, str(VERSIONS_DIR), options)
                import subprocess
                subprocess.Popen(command, cwd=str(game_dir))
                self.log("Minecraft запущен. Если версия/Java не совпадают, смотри сообщение об ошибке.")
            except Exception as e:
                self.log(f"Ошибка запуска: {e}")
        threading.Thread(target=worker, daemon=True).start()

    def search_mods(self):
        query = self.mod_query.get().strip()
        if not query:
            return
        self.mod_list.delete(0, "end")
        self.mod_results = []
        self.log(f"Поиск Modrinth: {query}")
        def worker():
            try:
                params = urllib.parse.urlencode({"query": query, "limit": 30, "facets": json.dumps([["project_type:mod"]])})
                data = get_json(f"{MODRINTH_API}/search?{params}")
                self.mod_results = data.get("hits", [])
                for hit in self.mod_results:
                    label = f'{hit.get("title","?")} — {hit.get("author","?")} | {hit.get("description","")[:90]}'
                    self.after(0, lambda s=label: self.mod_list.insert("end", s))
                self.log(f"Найдено проектов: {len(self.mod_results)}")
            except Exception as e:
                self.log(f"Ошибка поиска Modrinth: {e}")
        threading.Thread(target=worker, daemon=True).start()

    def download_mod(self):
        selection = self.mod_list.curselection()
        if not selection:
            messagebox.showinfo("BlockLaunch", "Выбери мод в списке.")
            return
        hit = self.mod_results[selection[0]]
        version = self.version.get().strip()
        profile = self.profile_dir()
        mods_dir = profile / "mods"
        mods_dir.mkdir(parents=True, exist_ok=True)
        self.log(f"Получаю файлы {hit.get('title','мода')}…")
        def worker():
            try:
                versions = get_json(f"{MODRINTH_API}/project/{hit['project_id']}/version")
                # Prefer selected Minecraft version; if no match, take latest version and warn.
                matching = [v for v in versions if version in v.get("game_versions", [])]
                chosen = matching[0] if matching else (versions[0] if versions else None)
                if not chosen:
                    raise RuntimeError("У проекта нет доступных файлов.")
                primary = next((f for f in chosen.get("files", []) if f.get("primary")), chosen.get("files", [None])[0])
                if not primary:
                    raise RuntimeError("В выбранной версии не найден файл.")
                filename = Path(primary["filename"]).name
                target = mods_dir / filename
                target.write_bytes(open_url(primary["url"], timeout=120))
                self.log(f"Скачано: {target}")
                if not matching:
                    self.log("ВНИМАНИЕ: точного совпадения версии Minecraft не найдено. Проверь совместимость загрузчика/версии.")
            except Exception as e:
                self.log(f"Ошибка скачивания мода: {e}")
        threading.Thread(target=worker, daemon=True).start()

if __name__ == "__main__":
    try:
        import minecraft_launcher_lib  # noqa
    except ImportError:
        root = tk.Tk(); root.withdraw()
        messagebox.showinfo("BlockLaunch", "Устанавливаются компоненты лаунчера. Нужен интернет.")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "minecraft-launcher-lib>=7.1", "requests>=2.31"])
    Launcher().mainloop()
