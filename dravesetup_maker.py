"""
DraveSetup_Maker - Wizard om bestaande Windows .exe applicaties
naar een self-extracting installer-exe te bouwen.

Geen Nuitka, geen Python-compile. Werkt met al gecompileerde
.exe-bestanden (bv. eerder gemaakt via PySetup_Maker).

Voor persoonlijk gebruik en distributie. UI in Dravenlock-stijl
(zilver accent op antraciet, WCAG AAA contrast).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, QThread, QUrl
from PySide6.QtGui import QFont, QIcon, QPixmap, QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QLineEdit, QPushButton, QFileDialog,
    QPlainTextEdit, QListWidget, QMessageBox, QSplitter,
    QFrame, QSizePolicy, QProgressBar, QMenu, QDialog,
)

from core.styling import (
    COLOR, base_font, mono_font, title_font,
    app_stylesheet, primary_button_style, secondary_button_style,
    input_style, console_style, list_style, progressbar_style,
)
from core.scanner import scan_input, detect_extra_files
from core.builder import BuildWorker


APP_VERSION = "0.1.0"

# URLs (Dravenlock infrastructuur - single-page site met anchors)
# Update deze als de site live is en je de definitieve anchor-namen kent.
VERSION_CHECK_URL = "https://dravenlock.nl/downloads/dravesetup/version.txt"
DOWNLOAD_URL = "https://dravenlock.nl/#dravesetup"
DONATION_URL = "https://paypal.me/roger076"
CONTACT_URL = "https://dravenlock.nl/#contact"

# Het Dravenlock-logo wordt INGEBAKKEN als base64-string. Wordt bij
# build-tijd ingevuld door build_dravesetup_maker.bat (leest logo.png
# en injecteert hier). Bij development blijft 'ie leeg - dan
# valt de UI terug op een tekst-fallback.
EMBEDDED_LOGO_B64 = ""


class _LabelledField(QWidget):
    """Helper: label + invoerveld + bladeren-knop in 1 rij."""

    def __init__(self, label: str, button_text: str = "Bladeren...",
                 read_only: bool = False, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        lbl = QLabel(label)
        lbl.setFont(base_font(11))
        lbl.setStyleSheet(
            f"color: {COLOR.text}; background: transparent; "
            f"font-weight: bold;"
        )
        layout.addWidget(lbl)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.input = QLineEdit()
        self.input.setStyleSheet(input_style())
        self.input.setMinimumHeight(40)
        self.input.setReadOnly(read_only)
        row.addWidget(self.input, stretch=1)

        self.button = QPushButton(button_text)
        self.button.setStyleSheet(secondary_button_style())
        self.button.setMinimumHeight(40)
        self.button.setCursor(Qt.PointingHandCursor)
        row.addWidget(self.button)

        layout.addLayout(row)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"DraveSetup_Maker  v{APP_VERSION}")
        self.resize(1240, 760)
        self.setStyleSheet(app_stylesheet())

        self._build_ui()
        self._worker_thread: Optional[QThread] = None
        self._worker: Optional[BuildWorker] = None

    def _load_app_logo(self):
        """
        Laad het Dravenlock-logo voor de header.

        Volgorde:
        1. EMBEDDED_LOGO_B64 (ingebakken bij build) - werkt altijd,
           ongeacht waar de exe staat
        2. logo.png/logo.jpg in de exe-map (development fallback)
        3. Tekst-fallback "D"
        """
        from pathlib import Path
        import sys
        import base64 as _b64

        # 1. Embedded base64 - production mode (exe gebouwd via batch)
        if EMBEDDED_LOGO_B64:
            try:
                data = _b64.b64decode(EMBEDDED_LOGO_B64)
                pix = QPixmap()
                if pix.loadFromData(data) and not pix.isNull():
                    scaled = pix.scaled(
                        48, 48,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
                    self.logo_label.setPixmap(scaled)
                    self._logo_diag = ["Logo: ingebakken (base64)"]
                    return
            except Exception as e:
                # Bij decode-fout, val terug op file-zoek
                pass

        # 2. Filesystem - development mode (python dravesetup_maker.py)
        search_dirs = []
        try:
            argv0 = Path(sys.argv[0]).resolve()
            if argv0.is_file():
                search_dirs.append(argv0.parent)
            else:
                search_dirs.append(argv0)
        except Exception:
            pass
        try:
            search_dirs.append(Path(__file__).resolve().parent)
        except NameError:
            pass
        try:
            search_dirs.append(Path(sys.executable).resolve().parent)
        except Exception:
            pass
        try:
            search_dirs.append(Path.cwd())
        except Exception:
            pass

        # Dedupe
        seen = set()
        dirs = []
        for d in search_dirs:
            key = str(d).lower()
            if key not in seen:
                seen.add(key)
                dirs.append(d)

        self._logo_diag = ["Logo: ingebakken leeg, filesystem fallback"]
        for d in dirs:
            for name in ("logo.png", "logo.jpg",
                         "dravenlock_logo.png", "dravenlock_logo.jpg"):
                p = d / name
                if p.is_file():
                    pix = QPixmap(str(p))
                    if not pix.isNull():
                        scaled = pix.scaled(
                            48, 48,
                            Qt.KeepAspectRatio,
                            Qt.SmoothTransformation
                        )
                        self.logo_label.setPixmap(scaled)
                        self._logo_diag.append(f"Logo gevonden: {p}")
                        return

        # 3. Tekst-fallback
        self.logo_label.setText("D")
        self.logo_label.setStyleSheet(
            f"background: #000000; color: {COLOR.accent}; "
            f"font-size: 20pt; font-weight: bold; "
            f"border-radius: 6px;"
        )
        self._logo_diag.append("Geen logo gevonden - tekst-fallback.")

        # Geen logo gevonden: toon een kleine "D" als fallback
        self.logo_label.setText("D")
        self.logo_label.setStyleSheet(
            f"background: #000000; color: {COLOR.accent}; "
            f"font-size: 20pt; font-weight: bold; "
            f"border-radius: 6px;"
        )

    def _build_footer(self):
        """
        Footer onderaan: versie nummer | donatie | Over (menu).
        Het Over-menu heeft sub-items: Versie controle, Snelgids,
        Contact.
        """
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 8, 0, 0)
        footer.setSpacing(10)

        # Versie-label links
        ver_lbl = QLabel(f"v{APP_VERSION}")
        ver_lbl.setStyleSheet(
            f"color: {COLOR.text_dim}; background: transparent; "
            f"font-size: 10pt;"
        )
        footer.addWidget(ver_lbl)
        footer.addStretch()

        # Donatie-knop
        btn_donate = QPushButton("☕  Donatie")
        btn_donate.setStyleSheet(secondary_button_style())
        btn_donate.clicked.connect(self._on_donate)
        footer.addWidget(btn_donate)

        # Over-knop met dropdown
        btn_over = QPushButton("Over  ▾")
        btn_over.setStyleSheet(secondary_button_style())

        over_menu = QMenu(self)
        over_menu.setStyleSheet(
            f"QMenu {{ background: {COLOR.bg_card}; "
            f"color: {COLOR.text}; "
            f"border: 2px solid {COLOR.border}; "
            f"border-radius: 6px; padding: 4px; }} "
            f"QMenu::item {{ padding: 8px 24px; "
            f"border-radius: 4px; }} "
            f"QMenu::item:selected {{ "
            f"  background: {COLOR.accent_dim}; "
            f"  color: {COLOR.text}; }}"
        )
        over_menu.addAction("Versie controle",
                             self._on_version_check)
        over_menu.addAction("Snelgids", self._on_quick_guide)
        over_menu.addAction("Contact", self._on_contact)
        over_menu.addSeparator()
        over_menu.addAction("Over DraveSetup Maker", self._on_about)
        btn_over.setMenu(over_menu)
        footer.addWidget(btn_over)

        return footer

    def _on_donate(self):
        QDesktopServices.openUrl(QUrl(DONATION_URL))

    def _on_contact(self):
        QDesktopServices.openUrl(QUrl(CONTACT_URL))

    def _on_version_check(self):
        """
        Haal de nieuwste versie op van dravenlock.nl en vergelijk
        met huidige. Toont dialoog met resultaat.
        """
        try:
            import urllib.request
            req = urllib.request.Request(
                VERSION_CHECK_URL,
                headers={"User-Agent": "DraveSetupMaker/" + APP_VERSION}
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                latest = r.read().decode("utf-8").strip()
        except Exception as e:
            QMessageBox.warning(
                self, "Versie controle",
                "Kon de versie-informatie niet ophalen.\n\n"
                "Controleer je internet-verbinding.\n\n"
                f"Fout: {e}"
            )
            return

        if not latest:
            QMessageBox.warning(
                self, "Versie controle",
                "De server gaf een lege response terug."
            )
            return

        if self._compare_versions(latest, APP_VERSION) > 0:
            reply = QMessageBox.question(
                self, "Nieuwe versie beschikbaar",
                f"Er is een nieuwe versie beschikbaar!\n\n"
                f"Huidige versie: {APP_VERSION}\n"
                f"Nieuwste versie: {latest}\n\n"
                f"Wil je naar de download-pagina?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            if reply == QMessageBox.Yes:
                QDesktopServices.openUrl(QUrl(DOWNLOAD_URL))
        else:
            QMessageBox.information(
                self, "Versie controle",
                f"Je hebt de nieuwste versie.\n\n"
                f"Versie: {APP_VERSION}"
            )

    def _compare_versions(self, a: str, b: str) -> int:
        """
        Vergelijk twee versie-strings (bv '1.2.3' vs '1.2.4').
        Returns: -1 als a<b, 0 als gelijk, 1 als a>b.
        """
        def _parts(s):
            out = []
            for x in s.replace("v", "").split("."):
                try:
                    out.append(int(x))
                except ValueError:
                    out.append(0)
            return out
        pa, pb = _parts(a), _parts(b)
        # Pad korter met nullen
        while len(pa) < len(pb):
            pa.append(0)
        while len(pb) < len(pa):
            pb.append(0)
        for x, y in zip(pa, pb):
            if x < y:
                return -1
            if x > y:
                return 1
        return 0

    def _on_quick_guide(self):
        """Dialog met snelgids-tekst."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Snelgids - DraveSetup Maker")
        dlg.resize(620, 480)
        dlg.setStyleSheet(
            f"QDialog {{ background: {COLOR.bg_app}; }} "
            f"QLabel {{ color: {COLOR.text}; "
            f"background: transparent; }}"
        )
        v = QVBoxLayout(dlg)
        v.setContentsMargins(24, 20, 24, 20)
        v.setSpacing(12)

        title = QLabel("Snelgids")
        title.setStyleSheet(
            f"color: {COLOR.accent}; font-size: 18pt; "
            f"font-weight: bold; background: transparent;"
        )
        v.addWidget(title)

        guide_text = (
            "<b>1. App-map of losse .exe kiezen</b><br>"
            "Klik op 'Map kiezen...' als je app uit meerdere "
            "bestanden bestaat (een .exe samen met DLL's, configs "
            "of assets). Of klik op '.exe kiezen...' voor een "
            "self-contained losse .exe (bv. een Nuitka --onefile "
            "build). DraveSetup detecteert alles automatisch.<br><br>"

            "<b>2. Hoofd .exe</b><br>"
            "Het Windows-uitvoerbestand dat de app start. "
            "Wordt automatisch herkend op basis van veelgebruikte "
            "namen (main.exe, app.exe, &lt;mapnaam&gt;.exe).<br><br>"

            "<b>3. Icoon (.ico)</b><br>"
            "Het icoon van de app zelf. Wordt zichtbaar als "
            "exe-icoon van de geïnstalleerde app en op de "
            "snelkoppelingen.<br><br>"

            "<b>4. Merk-logo</b><br>"
            "Een PNG of JPG van je merk-logo. Wordt getoond in de "
            "installer-wizard banner én gebruikt voor het icoon "
            "van installer.exe en uninstall.exe.<br><br>"

            "<b>5. Extra bestanden</b><br>"
            "Bestanden die mee moeten met je app (DLL's, .pak "
            "files, configs, locale-mappen, assets). Worden "
            "automatisch gedetecteerd vanuit de app-map en "
            "komen naast de .exe in de install-locatie.<br><br>"

            "<b>6. Setup-naam en output-map</b><br>"
            "De naam van de installer.exe en waar 'ie komt te "
            "staan. Er wordt automatisch een versie-submap "
            "aangemaakt om Windows icon-cache te omzeilen.<br><br>"

            "<b>7. Maken</b><br>"
            "Klik op 'Maken' om de installer te bouwen. De console "
            "rechts toont de voortgang. Een build duurt 1-3 "
            "minuten - veel sneller dan PySetup omdat er geen "
            "Nuitka-compile stap is."
        )
        body = QLabel(guide_text)
        body.setWordWrap(True)
        body.setTextFormat(Qt.RichText)
        body.setStyleSheet(
            f"color: {COLOR.text}; background: transparent; "
            f"font-size: 10pt; line-height: 1.5;"
        )
        v.addWidget(body, stretch=1)

        btn = QPushButton("Sluiten")
        btn.setStyleSheet(primary_button_style())
        btn.clicked.connect(dlg.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn)
        v.addLayout(btn_row)

        dlg.exec()

    def _on_about(self):
        """Over-dialog met versie en korte beschrijving."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Over DraveSetup Maker")
        dlg.resize(480, 320)
        dlg.setStyleSheet(
            f"QDialog {{ background: {COLOR.bg_app}; }} "
            f"QLabel {{ color: {COLOR.text}; "
            f"background: transparent; }}"
        )
        v = QVBoxLayout(dlg)
        v.setContentsMargins(24, 20, 24, 20)
        v.setSpacing(10)

        title = QLabel("DraveSetup Maker")
        title.setStyleSheet(
            f"color: {COLOR.accent}; font-size: 20pt; "
            f"font-weight: bold; background: transparent;"
        )
        v.addWidget(title)

        version_lbl = QLabel(f"Versie {APP_VERSION}")
        version_lbl.setStyleSheet(
            f"color: {COLOR.text_dim}; font-size: 11pt;"
        )
        v.addWidget(version_lbl)

        v.addSpacing(8)

        about_text = (
            "Een eenvoudige tool die bestaande Windows .exe "
            "applicaties omzet naar self-extracting installers.\n\n"
            "Geen Nuitka, geen Python-compile. Werkt met elke "
            "al gecompileerde Windows-app (Nuitka, PyInstaller, "
            "Inno Setup output, of zelfgemaakte exe's).\n\n"
            "Eén klik en je app is klaar voor distributie.\n\n"
            "Een Dravenlock Software product."
        )
        body = QLabel(about_text)
        body.setWordWrap(True)
        body.setStyleSheet(
            f"color: {COLOR.text}; font-size: 10pt;"
        )
        v.addWidget(body, stretch=1)

        btn = QPushButton("Sluiten")
        btn.setStyleSheet(primary_button_style())
        btn.clicked.connect(dlg.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn)
        v.addLayout(btn_row)

        dlg.exec()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(20, 18, 20, 14)
        outer.setSpacing(12)

        # === Header: Dravenlock-logo links + titel rechts ===
        header = QHBoxLayout()
        header.setSpacing(14)

        self.logo_label = QLabel()
        self.logo_label.setFixedSize(48, 48)
        self.logo_label.setStyleSheet("background: transparent;")
        self.logo_label.setAlignment(Qt.AlignCenter)
        self._load_app_logo()
        header.addWidget(self.logo_label)

        title = QLabel("DraveSetup Maker")
        title.setFont(title_font(22))
        title.setStyleSheet(
            f"color: {COLOR.text}; background: transparent;"
        )
        header.addWidget(title)
        header.addStretch()

        outer.addLayout(header)

        # Splitter: links velden | rechts console
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(8)
        outer.addWidget(splitter, stretch=1)

        # === Linker paneel: invoervelden ===
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(14)

        # Input-bron: kan een MAP zijn (met .exe + DLL's + assets)
        # of een LOSSE .exe-file. Scanner detecteert automatisch.
        self.fld_project = _LabelledField(
            "App-map of losse .exe",
            "Map kiezen..."
        )
        self.fld_project.button.clicked.connect(self._on_pick_project)
        left_layout.addWidget(self.fld_project)

        # Tweede knop: losse .exe kiezen
        self.fld_input_exe = _LabelledField(
            "Of: kies direct een .exe bestand",
            ".exe kiezen..."
        )
        self.fld_input_exe.button.clicked.connect(self._on_pick_input_exe)
        left_layout.addWidget(self.fld_input_exe)

        # Hoofd .exe (auto-gedetecteerd, of handmatig wijzigen)
        self.fld_main = _LabelledField(
            "Hoofd .exe bestand",
            "Wijzigen..."
        )
        self.fld_main.button.clicked.connect(self._on_pick_main_exe)
        left_layout.addWidget(self.fld_main)

        # Icoon
        self.fld_icon = _LabelledField(
            "Icoon (.ico)",
            "Wijzigen..."
        )
        self.fld_icon.button.clicked.connect(self._on_pick_icon)
        left_layout.addWidget(self.fld_icon)

        # Merk-logo (Dravenlock) - apart van app-icon
        self.fld_brand_logo = _LabelledField(
            "Merk-logo (Dravenlock) - .png of .jpg",
            "Kiezen..."
        )
        self.fld_brand_logo.button.clicked.connect(self._on_pick_brand_logo)
        left_layout.addWidget(self.fld_brand_logo)

        # Extra bestanden (lijst + toevoegen/verwijderen)
        extras_label = QLabel("Extra bestanden / mappen")
        extras_label.setFont(base_font(11))
        extras_label.setStyleSheet(
            f"color: {COLOR.text}; background: transparent; "
            f"font-weight: bold;"
        )
        left_layout.addWidget(extras_label)

        self.list_extras = QListWidget()
        self.list_extras.setStyleSheet(list_style())
        self.list_extras.setMinimumHeight(110)
        left_layout.addWidget(self.list_extras)

        row_extras = QHBoxLayout()
        row_extras.setSpacing(8)
        btn_add_file = QPushButton("Bestand toevoegen")
        btn_add_file.setStyleSheet(secondary_button_style())
        btn_add_file.setCursor(Qt.PointingHandCursor)
        btn_add_file.clicked.connect(self._on_add_extra_file)
        row_extras.addWidget(btn_add_file)

        btn_add_dir = QPushButton("Map toevoegen")
        btn_add_dir.setStyleSheet(secondary_button_style())
        btn_add_dir.setCursor(Qt.PointingHandCursor)
        btn_add_dir.clicked.connect(self._on_add_extra_dir)
        row_extras.addWidget(btn_add_dir)

        btn_rm = QPushButton("Verwijderen")
        btn_rm.setStyleSheet(secondary_button_style())
        btn_rm.setCursor(Qt.PointingHandCursor)
        btn_rm.clicked.connect(self._on_remove_extra)
        row_extras.addWidget(btn_rm)
        row_extras.addStretch()
        left_layout.addLayout(row_extras)

        # Setup naam
        self.fld_setup_name = _LabelledField(
            "Naam van de installer (zonder .exe)",
            "Standaard"
        )
        self.fld_setup_name.button.clicked.connect(
            self._on_reset_setup_name
        )
        left_layout.addWidget(self.fld_setup_name)

        # Output-map waar de installer.exe komt
        self.fld_output = _LabelledField(
            "Output-map (waar komt de installer.exe?)",
            "Map kiezen..."
        )
        self.fld_output.button.clicked.connect(self._on_pick_output)
        left_layout.addWidget(self.fld_output)

        left_layout.addStretch()
        splitter.addWidget(left)

        # === Rechter paneel: console + actie-knoppen ===
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(10)

        console_label = QLabel("Build-output")
        console_label.setFont(base_font(11))
        console_label.setStyleSheet(
            f"color: {COLOR.text}; background: transparent; "
            f"font-weight: bold;"
        )
        right_layout.addWidget(console_label)

        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet(console_style())
        self.console.setFont(mono_font(10))
        self.console.appendPlainText(
            "DraveSetup_Maker klaar. Kies een project-map om te beginnen."
        )
        # Toon logo-detectie diagnostiek (eenmalig bij start)
        if hasattr(self, "_logo_diag") and self._logo_diag:
            self.console.appendPlainText("")
            self.console.appendPlainText("--- Logo-detectie diagnose ---")
            for line in self._logo_diag:
                self.console.appendPlainText(line)
            self.console.appendPlainText("")
        right_layout.addWidget(self.console, stretch=1)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setStyleSheet(progressbar_style())
        right_layout.addWidget(self.progress)

        # Actie-knoppen
        row_actions = QHBoxLayout()
        row_actions.setSpacing(10)
        row_actions.addStretch()

        self.btn_cancel = QPushButton("Annuleren")
        self.btn_cancel.setStyleSheet(secondary_button_style())
        self.btn_cancel.setMinimumHeight(44)
        self.btn_cancel.setMinimumWidth(140)
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._on_cancel)
        row_actions.addWidget(self.btn_cancel)

        self.btn_make = QPushButton("Maken")
        self.btn_make.setStyleSheet(primary_button_style())
        self.btn_make.setMinimumHeight(44)
        self.btn_make.setMinimumWidth(160)
        self.btn_make.setCursor(Qt.PointingHandCursor)
        self.btn_make.clicked.connect(self._on_make)
        row_actions.addWidget(self.btn_make)

        right_layout.addLayout(row_actions)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([580, 580])

        # === Footer (versie | donatie | over) ===
        outer.addLayout(self._build_footer())

    # === Event handlers ===

    def _on_pick_project(self):
        d = QFileDialog.getExistingDirectory(
            self, "Kies app-map (met .exe + DLL's + assets)",
            self.fld_project.input.text() or str(Path.home())
        )
        if not d:
            return
        self.fld_project.input.setText(d)
        # Leeg het losse-exe veld want we gebruiken map-mode
        self.fld_input_exe.input.setText("")
        self._auto_fill_from_input(d)

    def _on_pick_input_exe(self):
        """Kies een losse .exe-file (geen map nodig)."""
        start = self.fld_input_exe.input.text() or \
                self.fld_project.input.text() or str(Path.home())
        f, _ = QFileDialog.getOpenFileName(
            self, "Kies een .exe bestand", start,
            "Windows-applicaties (*.exe)"
        )
        if not f:
            return
        self.fld_input_exe.input.setText(f)
        # Leeg het map-veld want we gebruiken file-mode
        self.fld_project.input.setText("")
        self._auto_fill_from_input(f)

    def _auto_fill_from_input(self, path: str):
        """
        Scan input (map of losse .exe) en vul de andere velden
        automatisch in. scan_input regelt beide modi.
        """
        mode, main_exe, icon, all_exes = scan_input(path)

        if mode is None:
            self._log(f"Kon input niet herkennen: {path}")
            return

        if mode == "file":
            self._log(f"Mode: losse .exe-file")
        else:
            self._log(f"Mode: app-map met {len(all_exes)} .exe-bestand(en)")

        if main_exe:
            self.fld_main.input.setText(main_exe)
            self._log(f"Hoofd .exe gevonden: {Path(main_exe).name}")
        else:
            self.fld_main.input.setText("")
            self._log(
                f"Geen duidelijke hoofd-.exe gevonden. "
                f"Beschikbare .exe: {', '.join(all_exes) or '(geen)'}"
            )

        if icon:
            self.fld_icon.input.setText(icon)
            self._log(f"Icoon gevonden: {Path(icon).name}")
        else:
            self.fld_icon.input.setText("")
            self._log("Geen .ico gevonden - geen icoon gebruikt.")

        # Auto-detect merk-logo in de hoofd-map
        scan_dir = (Path(path) if mode == "folder"
                    else Path(path).parent)
        if not self.fld_brand_logo.input.text():
            for name in ("logo.png", "logo.jpg", "logo.jpeg",
                         "dravenlock_logo.png", "dravenlock_logo.jpg",
                         "dravenlock_logo.jpeg"):
                p = scan_dir / name
                if p.is_file():
                    self.fld_brand_logo.input.setText(str(p))
                    self._log(f"Merk-logo gevonden: {p.name}")
                    break

        # Extra's voorstellen - alleen in folder-mode
        self.list_extras.clear()
        if mode == "folder" and main_exe:
            extras = detect_extra_files(str(scan_dir), main_exe, icon)
            for e in extras:
                self.list_extras.addItem(e)
            if extras:
                self._log(
                    f"{len(extras)} extra bestanden / mappen "
                    f"voorgesteld (verwijder wat niet hoort)."
                )
        elif mode == "file":
            self._log(
                "Losse .exe-mode: voeg handmatig extra "
                "bestanden toe als de app DLL's of assets nodig "
                "heeft."
            )

        # Setup-naam default
        if not self.fld_setup_name.input.text():
            if main_exe:
                base = Path(main_exe).stem
            else:
                base = scan_dir.name
            self.fld_setup_name.input.setText(f"{base}_setup")

        # Output-map default
        if not self.fld_output.input.text():
            self.fld_output.input.setText(str(scan_dir / "installer"))

    def _on_pick_output(self):
        start = self.fld_output.input.text() or str(Path.home())
        d = QFileDialog.getExistingDirectory(
            self, "Output-map voor de installer", start
        )
        if d:
            self.fld_output.input.setText(d)

    def _on_pick_main_exe(self):
        start = self.fld_project.input.text() or \
                self.fld_input_exe.input.text() or str(Path.home())
        f, _ = QFileDialog.getOpenFileName(
            self, "Hoofd .exe bestand", start,
            "Windows-applicaties (*.exe);;Alle bestanden (*)"
        )
        if f:
            self.fld_main.input.setText(f)

    def _on_pick_icon(self):
        start = self.fld_project.input.text() or str(Path.home())
        f, _ = QFileDialog.getOpenFileName(
            self, "Icoon (.ico)", start,
            "Icoon (*.ico);;Alle bestanden (*)"
        )
        if f:
            self.fld_icon.input.setText(f)

    def _on_pick_brand_logo(self):
        start = (self.fld_brand_logo.input.text()
                 or self.fld_project.input.text()
                 or str(Path.home()))
        if start and Path(start).is_file():
            start = str(Path(start).parent)
        f, _ = QFileDialog.getOpenFileName(
            self, "Merk-logo (Dravenlock)", start,
            "Afbeelding (*.png *.jpg *.jpeg);;Alle bestanden (*)"
        )
        if f:
            self.fld_brand_logo.input.setText(f)

    def _on_add_extra_file(self):
        start = self.fld_project.input.text() or str(Path.home())
        files, _ = QFileDialog.getOpenFileNames(
            self, "Extra bestanden", start
        )
        for f in files:
            self.list_extras.addItem(f)

    def _on_add_extra_dir(self):
        start = self.fld_project.input.text() or str(Path.home())
        d = QFileDialog.getExistingDirectory(
            self, "Extra map", start
        )
        if d:
            self.list_extras.addItem(d)

    def _on_remove_extra(self):
        for item in self.list_extras.selectedItems():
            self.list_extras.takeItem(self.list_extras.row(item))

    def _on_reset_setup_name(self):
        folder = self.fld_project.input.text()
        if folder:
            self.fld_setup_name.input.setText(
                f"{Path(folder).name}_setup"
            )

    # === Build flow ===

    def _log(self, msg: str):
        self.console.appendPlainText(msg)

    def _validate(self) -> Optional[str]:
        """Returns foutmelding of None."""
        main_exe = self.fld_main.input.text().strip()
        if not main_exe or not Path(main_exe).is_file():
            return "Geef een geldig hoofd-.exe bestand op."
        if Path(main_exe).suffix.lower() != ".exe":
            return "Het hoofd-bestand moet een .exe zijn."
        setup_name = self.fld_setup_name.input.text().strip()
        if not setup_name:
            return "Geef een naam voor de installer op."
        # Geen ongeldige chars
        bad = set('<>:"/\\|?*')
        if any(c in setup_name for c in bad):
            return ("Setup-naam mag geen van deze tekens bevatten: "
                    '< > : " / \\ | ? *')
        icon = self.fld_icon.input.text().strip()
        if icon and not Path(icon).is_file():
            return "Het opgegeven icoon-bestand bestaat niet."
        return None

    def _on_make(self):
        err = self._validate()
        if err:
            QMessageBox.warning(self, "Niet compleet", err)
            return

        main_exe = self.fld_main.input.text().strip()
        icon = self.fld_icon.input.text().strip() or None
        brand_logo = self.fld_brand_logo.input.text().strip() or None
        setup_name = self.fld_setup_name.input.text().strip()
        # project_folder: alleen relevant bij map-mode. Bij losse exe
        # mode is dit None (builder werkt prima zonder).
        project_folder = self.fld_project.input.text().strip() or None

        # Extra bestanden
        extras: List[str] = []
        for i in range(self.list_extras.count()):
            extras.append(self.list_extras.item(i).text())

        # Output-map = wat in het veld staat, anders fallback
        output_folder = self.fld_output.input.text().strip()
        if not output_folder:
            fallback = project_folder or str(Path(main_exe).parent)
            output_folder = str(Path(fallback) / "installer")

        # Reset console + progress
        self.console.clear()
        self.progress.setValue(0)
        self._log(f"=== Build starten: {setup_name} ===")
        self._log(f"Project    : {project_folder or '(losse .exe mode)'}")
        self._log(f"Hoofd .exe : {main_exe}")
        self._log(f"Icoon      : {icon or '(geen)'}")
        self._log(f"Merk-logo  : {brand_logo or '(geen)'}")
        self._log(f"Extras     : {len(extras)} stuks")
        self._log(f"Output     : {output_folder}")
        self._log("")

        # UI in build-mode
        self._set_building(True)

        # Worker op een achtergrond-thread
        self._worker_thread = QThread()
        self._worker = BuildWorker(
            project_folder=project_folder,
            main_exe=main_exe,
            icon=icon,
            brand_logo=brand_logo,
            extra_files=extras,
            setup_name=setup_name,
            output_folder=output_folder,
            app_display_name=setup_name.replace("_setup", "")
                                       .replace("-setup", ""),
        )
        self._worker.moveToThread(self._worker_thread)
        self._worker.log_message.connect(self._log)
        self._worker.progress.connect(self.progress.setValue)
        self._worker.finished.connect(self._on_build_done)
        self._worker_thread.started.connect(self._worker.run)
        self._worker_thread.start()

    def _on_cancel(self):
        if self._worker is not None:
            self._log("")
            self._log(">>> Annuleren aangevraagd...")
            self._worker.cancel()

    def _on_build_done(self, ok: bool, info: str):
        if self._worker_thread is not None:
            self._worker_thread.quit()
            self._worker_thread.wait()
        self._worker_thread = None
        self._worker = None
        self._set_building(False)

        if ok:
            self.progress.setValue(100)
            QMessageBox.information(
                self, "Klaar",
                f"Installer succesvol gemaakt:\n\n{info}"
            )
        else:
            QMessageBox.warning(
                self, "Mislukt",
                f"Build is niet voltooid:\n\n{info}"
            )

    def _set_building(self, building: bool):
        self.btn_make.setEnabled(not building)
        self.btn_cancel.setEnabled(building)
        self.fld_project.button.setEnabled(not building)
        self.fld_main.button.setEnabled(not building)
        self.fld_icon.button.setEnabled(not building)
        self.fld_brand_logo.button.setEnabled(not building)
        self.fld_output.button.setEnabled(not building)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("DraveSetup_Maker")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
