import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from main_window import MainWindow


def main():
    app = QApplication.instance()
    owns_app = app is None
    if owns_app:
        app = QApplication(sys.argv)

    QGuiApplication.styleHints().setColorScheme(Qt.ColorScheme.Light)
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    if owns_app:
        sys.exit(app.exec())
    return window


if __name__ == "__main__":
    main()
