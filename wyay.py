#!/usr/bin/env python3
"""wyay - a small graphical AUR package browser for Arch Linux."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

from PySide6.QtCore import QEvent, QThread, QSize, Qt, Signal
from PySide6.QtGui import QDesktopServices, QPalette
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QProgressBar,
    QVBoxLayout, QWidget, QSizePolicy,
)

APP_NAME = "wyay"
AUR_RPC = "https://aur.archlinux.org/rpc/v5/search?arg={}&by=name-desc"


@dataclass(frozen=True)
class Package:
    name: str
    version: str
    description: str
    votes: int
    popularity: float
    url: str

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Package":
        return cls(
            name=data.get("Name", ""), version=data.get("Version", ""),
            description=data.get("Description") or "Без описания",
            votes=int(data.get("NumVotes", 0)),
            popularity=float(data.get("Popularity", 0)),
            url=data.get("URL") or f"https://aur.archlinux.org/packages/{data.get('Name', '')}",
        )


class SearchWorker(QThread):
    results_ready = Signal(list)
    failed = Signal(str)

    def __init__(self, query: str) -> None:
        super().__init__()
        self.query = query

    def run(self) -> None:
        try:
            request = Request(AUR_RPC.format(quote(self.query)), headers={"User-Agent": "wyay/1.0"})
            with urlopen(request, timeout=12) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if payload.get("type") != "search":
                raise RuntimeError(payload.get("error", "AUR вернул неизвестный ответ"))
            self.results_ready.emit([Package.from_api(item) for item in payload.get("results", [])])
        except Exception as error:  # noqa: BLE001 - shown to the user
            self.failed.emit(str(error))


class PackageRow(QFrame):
    def __init__(self, package: Package) -> None:
        super().__init__()
        self.setObjectName("packageRow")
        self.setMinimumHeight(88)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(16)
        info = QVBoxLayout()
        info.setSpacing(4)
        title = QLabel(package.name)
        title.setObjectName("packageName")
        meta = QLabel(f"{package.version}  ·  ★ {package.votes}  ·  {package.popularity:.2f} popularity")
        meta.setObjectName("packageMeta")
        description = QLabel(package.description)
        description.setObjectName("packageDescription")
        description.setWordWrap(True)
        description.setMinimumHeight(36)
        info.addWidget(title)
        info.addWidget(meta)
        info.addWidget(description)
        layout.addLayout(info, 1)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.worker: SearchWorker | None = None
        self.results: list[Package] = []
        self.selected_package: Package | None = None
        self._updating_palette = False
        self.setWindowTitle("wyay — AUR package browser")
        self.setMinimumSize(760, 560)
        self.resize(900, 680)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        main = QVBoxLayout(root)
        main.setContentsMargins(34, 30, 34, 26)
        main.setSpacing(18)
        header = QHBoxLayout()
        brand = QVBoxLayout()
        brand.setSpacing(2)
        logo = QLabel("wyay")
        logo.setObjectName("logo")
        subtitle = QLabel("Пакеты Arch User Repository")
        subtitle.setObjectName("subtitle")
        brand.addWidget(logo)
        brand.addWidget(subtitle)
        header.addLayout(brand)
        header.addStretch()
        self.status = QLabel("Готов к поиску")
        self.status.setObjectName("status")
        header.addWidget(self.status, alignment=Qt.AlignmentFlag.AlignTop)
        main.addLayout(header)
        search_line = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setObjectName("searchInput")
        self.search.setPlaceholderText("Найти пакет по имени или описанию…")
        self.search.setClearButtonEnabled(True)
        self.search.returnPressed.connect(self.search_packages)
        search_line.addWidget(self.search, 1)
        self.search_button = QPushButton("Поиск")
        self.search_button.setObjectName("searchButton")
        self.search_button.clicked.connect(self.search_packages)
        search_line.addWidget(self.search_button)
        main.addLayout(search_line)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedHeight(3)
        self.progress.hide()
        main.addWidget(self.progress)
        content = QHBoxLayout()
        content.setSpacing(14)
        self.list = QListWidget()
        self.list.setObjectName("packageList")
        self.list.setFrameShape(QFrame.Shape.NoFrame)
        self.list.setSpacing(10)
        self.list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.list.setMinimumWidth(330)
        self.list.currentRowChanged.connect(self._select_package)
        content.addWidget(self.list, 2)

        self.details = QFrame()
        self.details.setObjectName("detailsPanel")
        details_layout = QVBoxLayout(self.details)
        details_layout.setContentsMargins(24, 22, 24, 22)
        details_layout.setSpacing(10)
        self.detail_empty = QLabel("Выберите пакет в списке")
        self.detail_empty.setObjectName("detailEmpty")
        self.detail_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        details_layout.addWidget(self.detail_empty, 1)
        self.detail_title = QLabel()
        self.detail_title.setObjectName("detailTitle")
        self.detail_title.setWordWrap(True)
        self.detail_meta = QLabel()
        self.detail_meta.setObjectName("packageMeta")
        self.detail_description = QLabel()
        self.detail_description.setObjectName("packageDescription")
        self.detail_description.setWordWrap(True)
        self.detail_description.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.detail_stats = QLabel()
        self.detail_stats.setObjectName("detailStats")
        self.detail_stats.setWordWrap(True)
        self.open_button = QPushButton("Открыть страницу AUR")
        self.open_button.setObjectName("secondaryButton")
        self.open_button.clicked.connect(self._open_selected_url)
        for widget in (self.detail_title, self.detail_meta, self.detail_description, self.detail_stats, self.open_button):
            widget.hide()
            details_layout.addWidget(widget)
        details_layout.addStretch(1)
        content.addWidget(self.details, 3)
        main.addLayout(content, 1)

        self.empty = QLabel("Введите название пакета и нажмите «Поиск»")
        self.empty.setObjectName("emptyState")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.hide()
        main.addWidget(self.empty)
        self.install_button = QPushButton("Выберите пакет для установки")
        self.install_button.setObjectName("installButton")
        self.install_button.setEnabled(False)
        self.install_button.clicked.connect(self._install_selected)
        main.addWidget(self.install_button)
        footer = QLabel("Установка запускается через yay в терминале foot")
        footer.setObjectName("footer")
        main.addWidget(footer, alignment=Qt.AlignmentFlag.AlignCenter)

    def search_packages(self) -> None:
        query = self.search.text().strip()
        if not query:
            self._show_message("Введите название или часть названия пакета.")
            self.search.setFocus()
            return
        if self.worker and self.worker.isRunning():
            return
        self.status.setText("Ищу…")
        self.search_button.setEnabled(False)
        self.progress.show()
        self.empty.hide()
        self.list.clear()
        self._clear_details()
        self.worker = SearchWorker(query)
        self.worker.results_ready.connect(self._show_results)
        self.worker.failed.connect(self._search_failed)
        self.worker.finished.connect(self._search_finished)
        self.worker.start()

    def _show_results(self, packages: list[Package]) -> None:
        self.results = packages
        if not packages:
            self.empty.setText("Ничего не найдено. Попробуйте другой запрос.")
            self.empty.show()
            self.status.setText("0 пакетов")
            return
        for package in packages:
            row = PackageRow(package)
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, package)
            item.setSizeHint(QSize(0, 88))
            self.list.addItem(item)
            self.list.setItemWidget(item, row)
        self.list.setCurrentRow(0)
        self.status.setText(f"{len(packages)} пакетов")

    def _select_package(self, row: int) -> None:
        for index in range(self.list.count()):
            package_row = self.list.itemWidget(self.list.item(index))
            if package_row:
                package_row.setProperty("selected", index == row)
                package_row.style().unpolish(package_row)
                package_row.style().polish(package_row)
        if row < 0 or row >= len(self.results):
            self._clear_details()
            return
        package = self.results[row]
        self.selected_package = package
        self.detail_empty.hide()
        self.detail_title.setText(package.name)
        self.detail_meta.setText(package.version)
        self.detail_description.setText(package.description)
        self.detail_stats.setText(f"★ {package.votes} голосов\nПопулярность: {package.popularity:.2f}")
        for widget in (self.detail_title, self.detail_meta, self.detail_description, self.detail_stats, self.open_button):
            widget.show()
        self.install_button.setEnabled(True)
        self.install_button.setText(f"Установить {package.name}")

    def _clear_details(self) -> None:
        self.selected_package = None
        self.detail_empty.show()
        for widget in (self.detail_title, self.detail_meta, self.detail_description, self.detail_stats, self.open_button):
            widget.hide()
        self.install_button.setEnabled(False)
        self.install_button.setText("Выберите пакет для установки")

    def _search_failed(self, message: str) -> None:
        self.empty.setText("Не удалось получить данные AUR.")
        self.empty.show()
        self.status.setText("Ошибка соединения")
        self._show_message(f"AUR недоступен:\n{message}", error=True)

    def _search_finished(self) -> None:
        self.progress.hide()
        self.search_button.setEnabled(True)

    def _install_selected(self) -> None:
        if self.selected_package:
            self.install_package(self.selected_package.name)

    def install_package(self, name: str) -> None:
        answer = QMessageBox.question(self, "Установить пакет?", f"Запустить установку «{name}» через yay?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            subprocess.Popen(["foot", "-e", "yay", "-S", "--needed", name])
            self.status.setText(f"Установка {name} запущена")
        except FileNotFoundError:
            self._show_message("Не найден foot. Установите foot или измените команду запуска в wyay.py.", error=True)
        except OSError as error:
            self._show_message(f"Не удалось запустить установку:\n{error}", error=True)

    def open_url(self, url: str) -> None:
        QDesktopServices.openUrl(url)

    def _open_selected_url(self) -> None:
        if self.selected_package:
            self.open_url(self.selected_package.url)

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.PaletteChange and not self._updating_palette:
            app = QApplication.instance()
            if app:
                self._updating_palette = True
                try:
                    app.setStyleSheet(build_stylesheet(app.palette()))
                finally:
                    self._updating_palette = False

    def _show_message(self, text: str, error: bool = False) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Critical if error else QMessageBox.Icon.Information)
        box.setText(text)
        box.exec()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyleSheet(build_stylesheet(app.palette()))
    window = MainWindow()
    window.show()
    return app.exec()


def build_stylesheet(palette: QPalette) -> str:
    window = palette.color(QPalette.ColorRole.Window).name()
    base = palette.color(QPalette.ColorRole.Base).name()
    text = palette.color(QPalette.ColorRole.Text).name()
    muted = palette.color(QPalette.ColorRole.PlaceholderText).name()
    border = palette.color(QPalette.ColorRole.Mid).name()
    accent = palette.color(QPalette.ColorRole.Highlight).name()
    accent_text = palette.color(QPalette.ColorRole.HighlightedText).name()
    button = palette.color(QPalette.ColorRole.Button).name()
    return f"""
QMainWindow, QWidget {{ background: {window}; color: {text}; font-family: sans-serif; }}
QLabel {{ background: transparent; }}
#logo {{ color: {accent}; font-size: 32px; font-weight: 800; }}
#subtitle, #footer, #packageMeta {{ color: {muted}; }}
#subtitle {{ font-size: 13px; }}
#status {{ color: {muted}; font-size: 13px; padding-top: 9px; }}
#searchInput {{ background: {base}; border: 1px solid {border}; border-radius: 9px; padding: 12px 14px; font-size: 14px; }}
#searchInput:focus {{ border: 1px solid {accent}; }}
QPushButton {{ border: 0; border-radius: 8px; padding: 10px 17px; font-weight: 700; }}
#searchButton, #installButton {{ background: {accent}; color: {accent_text}; }}
#searchButton:hover, #installButton:hover {{ background: {accent}; }}
#secondaryButton {{ background: {button}; color: {text}; border: 1px solid {border}; }}
#secondaryButton:hover {{ border: 1px solid {accent}; }}
#packageList {{ background: transparent; padding: 2px; }}
#packageList::item {{ background: transparent; border: 0; padding: 0; margin: 0 0 8px 0; }}
#packageList::item:selected {{ background: transparent; }}
#packageRow {{ background: {base}; border: 1px solid {border}; border-radius: 12px; }}
#packageRow[selected="true"] {{ border: 2px solid {accent}; }}
#packageName {{ font-size: 16px; font-weight: 750; color: {accent}; }}
#packageDescription {{ color: {text}; font-size: 13px; }}
#detailsPanel {{ background: {base}; border: 1px solid {border}; border-radius: 12px; }}
#detailTitle {{ color: {accent}; font-size: 25px; font-weight: 800; }}
#detailStats {{ color: {muted}; }}
#emptyState {{ color: {muted}; font-size: 15px; padding: 26px; }}
#detailEmpty {{ color: {muted}; font-size: 15px; padding: 18px; }}
QProgressBar {{ background: {window}; border: 0; }}
QProgressBar::chunk {{ background: {accent}; }}
QScrollBar:vertical {{ background: transparent; width: 8px; }}
QScrollBar::handle:vertical {{ background: {border}; border-radius: 4px; }}
"""


if __name__ == "__main__":
    raise SystemExit(main())
