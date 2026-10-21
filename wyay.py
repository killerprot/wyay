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

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QProgressBar,
    QVBoxLayout, QWidget,
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
    install_requested = Signal(str)
    open_requested = Signal(str)

    def __init__(self, package: Package) -> None:
        super().__init__()
        self.setObjectName("packageRow")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 14, 14, 14)
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
        description.setMaximumHeight(42)
        info.addWidget(title)
        info.addWidget(meta)
        info.addWidget(description)
        layout.addLayout(info, 1)
        details = QPushButton("Открыть")
        details.setObjectName("secondaryButton")
        details.clicked.connect(lambda: self.open_requested.emit(package.url))
        install = QPushButton("Установить")
        install.setObjectName("installButton")
        install.clicked.connect(lambda: self.install_requested.emit(package.name))
        actions = QVBoxLayout()
        actions.setSpacing(7)
        actions.addWidget(details)
        actions.addWidget(install)
        layout.addLayout(actions)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.worker: SearchWorker | None = None
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
        self.list = QListWidget()
        self.list.setObjectName("packageList")
        self.list.setFrameShape(QFrame.Shape.NoFrame)
        self.list.setSpacing(10)
        self.list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        main.addWidget(self.list, 1)
        self.empty = QLabel("Введите название пакета и нажмите «Поиск»")
        self.empty.setObjectName("emptyState")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main.addWidget(self.empty)
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
        self.worker = SearchWorker(query)
        self.worker.results_ready.connect(self._show_results)
        self.worker.failed.connect(self._search_failed)
        self.worker.finished.connect(self._search_finished)
        self.worker.start()

    def _show_results(self, packages: list[Package]) -> None:
        if not packages:
            self.empty.setText("Ничего не найдено. Попробуйте другой запрос.")
            self.empty.show()
            self.status.setText("0 пакетов")
            return
        for package in packages:
            row = PackageRow(package)
            row.install_requested.connect(self.install_package)
            row.open_requested.connect(self.open_url)
            item = QListWidgetItem()
            item.setSizeHint(row.sizeHint())
            self.list.addItem(item)
            self.list.setItemWidget(item, row)
        self.status.setText(f"{len(packages)} пакетов")

    def _search_failed(self, message: str) -> None:
        self.empty.setText("Не удалось получить данные AUR.")
        self.empty.show()
        self.status.setText("Ошибка соединения")
        self._show_message(f"AUR недоступен:\n{message}", error=True)

    def _search_finished(self) -> None:
        self.progress.hide()
        self.search_button.setEnabled(True)

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

    def _show_message(self, text: str, error: bool = False) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Critical if error else QMessageBox.Icon.Information)
        box.setText(text)
        box.exec()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyleSheet(STYLESHEET)
    window = MainWindow()
    window.show()
    return app.exec()


STYLESHEET = """
QMainWindow, QWidget { background: #101114; color: #f2f3f5; font-family: sans-serif; }
#logo { color: #f6c344; font-size: 32px; font-weight: 800; }
#subtitle, #footer, #packageMeta { color: #8c929e; }
#subtitle { font-size: 13px; }
#status { color: #9da5b3; font-size: 13px; padding-top: 9px; }
#searchInput { background: #1c1f25; border: 1px solid #353b46; border-radius: 9px; padding: 12px 14px; font-size: 14px; }
#searchInput:focus { border: 1px solid #f6c344; }
QPushButton { border: 0; border-radius: 8px; padding: 10px 17px; font-weight: 700; }
#searchButton, #installButton { background: #f6c344; color: #1a1608; }
#searchButton:hover, #installButton:hover { background: #ffd96e; }
#secondaryButton { background: #292e37; color: #dce0e6; }
#secondaryButton:hover { background: #363d49; }
#packageList { background: transparent; }
#packageRow { background: #191c21; border: 1px solid #292f38; border-radius: 11px; }
#packageRow:hover { border: 1px solid #454d5b; }
#packageName { font-size: 16px; font-weight: 750; color: #f6c344; }
#packageDescription { color: #c1c6cf; font-size: 13px; }
#emptyState { color: #747c8a; font-size: 15px; padding: 50px; }
QProgressBar { background: #101114; border: 0; }
QProgressBar::chunk { background: #f6c344; }
QScrollBar:vertical { background: transparent; width: 8px; }
QScrollBar::handle:vertical { background: #3b424d; border-radius: 4px; }
"""


if __name__ == "__main__":
    raise SystemExit(main())
