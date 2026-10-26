"""
core/scanner.py - Scan voor de hoofd .exe en bijbehorende bestanden.

Twee scenarios:

1) Input is een LOSSE .exe-file:
   - hoofd .exe = die file zelf
   - geen extras (gebruiker kan handmatig toevoegen)
   - icoon = wordt geprobeerd uit dezelfde map: <naam>.ico of icon.ico

2) Input is een MAP met .exe + bijbehorende bestanden:
   - hoofd .exe = via heuristieken (zie hieronder)
   - extras = andere bestanden in de map (DLL's, configs, assets)
   - icoon = .ico in de map

Heuristieken voor hoofd-exe (van best naar minst):
  1. main.exe
  2. app.exe
  3. <mapnaam>.exe (bv. DeskButler/DeskButler.exe)
  4. run.exe / start.exe / launcher.exe
  5. Enige .exe in de root (als er maar 1 is)
  6. Grootste .exe (vaak het hoofd-programma)
"""
from pathlib import Path
from typing import Optional, Tuple, List


_MAIN_EXE_PREFERENCES = (
    "main.exe",
    "app.exe",
    "run.exe",
    "start.exe",
    "launcher.exe",
)


def scan_input(path: str) -> Tuple[Optional[str], Optional[str],
                                    Optional[str], List[str]]:
    """
    Scan een input-pad. Kan zowel een losse .exe als een map zijn.

    Returns:
        (input_mode, hoofd_exe_pad, icon_pad, lijst_van_extras)

    input_mode is "file" of "folder" of None als niets gevonden.
    """
    p = Path(path)
    if not p.exists():
        return None, None, None, []

    # ============ Mode 1: losse .exe file ============
    if p.is_file() and p.suffix.lower() == ".exe":
        # Probeer een .ico in dezelfde map (eerst <naam>.ico,
        # dan icon.ico, dan elke .ico)
        parent = p.parent
        icon = None
        candidates = [parent / (p.stem + ".ico"),
                      parent / "icon.ico"]
        for c in candidates:
            if c.is_file():
                icon = c
                break
        if icon is None:
            ico_files = sorted([f for f in parent.iterdir()
                                if f.is_file()
                                and f.suffix.lower() == ".ico"])
            if ico_files:
                icon = ico_files[0]

        return ("file", str(p),
                str(icon) if icon else None,
                [])  # geen extras voor losse file mode

    # ============ Mode 2: map met .exe + assets ============
    if p.is_dir():
        # Verzamel alle .exe-bestanden in de root (niet in subdirs)
        exe_files = sorted([f for f in p.iterdir()
                            if f.is_file()
                            and f.suffix.lower() == ".exe"])

        main_exe: Optional[Path] = None

        # 1. Voorkeurslijst
        for pref in _MAIN_EXE_PREFERENCES:
            candidate = p / pref
            if candidate.is_file():
                main_exe = candidate
                break

        # 2. <mapnaam>.exe (bv. DeskButler/DeskButler.exe)
        if main_exe is None:
            candidate = p / f"{p.name}.exe"
            if candidate.is_file():
                main_exe = candidate

        # 3. Enige .exe
        if main_exe is None and len(exe_files) == 1:
            main_exe = exe_files[0]

        # 4. Grootste .exe (heuristiek: hoofd-app is meestal het grootst)
        if main_exe is None and exe_files:
            main_exe = max(exe_files, key=lambda f: f.stat().st_size)

        # Icoon: <hoofd>.ico, icon.ico, of eerste .ico
        icon = None
        if main_exe is not None:
            same_name = p / (main_exe.stem + ".ico")
            if same_name.is_file():
                icon = same_name
        if icon is None:
            generic = p / "icon.ico"
            if generic.is_file():
                icon = generic
        if icon is None:
            ico_files = sorted([f for f in p.iterdir()
                                if f.is_file()
                                and f.suffix.lower() == ".ico"])
            if ico_files:
                icon = ico_files[0]

        return ("folder",
                str(main_exe) if main_exe else None,
                str(icon) if icon else None,
                [str(f.name) for f in exe_files])

    # Geen geldig type
    return None, None, None, []


def detect_extra_files(folder: str, main_exe: str,
                       icon: Optional[str]) -> List[str]:
    """
    Detecteer welke extra bestanden mogelijk bij de app horen.

    Sluit uit:
    - de hoofd .exe
    - het icoon (komt apart mee als app-icon)
    - typische build-output mappen
    - install_manifest.txt (van een vorige install)

    Alle andere bestanden + sub-mappen worden meegenomen als
    "moet in payload mee". Denk aan: DLL's, .pak files, config.json,
    locale-mappen, assets, plugins, README's, etc.
    """
    p = Path(folder)
    if not p.is_dir():
        return []

    excluded_names = set()
    if main_exe:
        excluded_names.add(Path(main_exe).name)
    if icon:
        excluded_names.add(Path(icon).name)
    excluded_names.add("install_manifest.txt")

    excluded_dirs = {
        "__pycache__", "build", "dist", ".git",
        ".venv", "venv", ".idea", ".vscode",
        "build_output", "build_output_debug",
        "build_output_folder", "node_modules",
        "_brand_assets", "_build_temp"
    }

    extras: List[str] = []
    for item in sorted(p.iterdir()):
        if item.name in excluded_names:
            continue
        if item.name.startswith("."):
            continue
        if item.is_dir() and item.name in excluded_dirs:
            continue
        if item.suffix.lower() in (".pyc", ".pyo"):
            continue
        # Skip eerdere installer-output (.exe die niet de hoofd-exe is)
        if item.suffix.lower() == ".exe":
            continue
        extras.append(str(item))

    return extras
