import sys

from PySide6.QtWidgets import QApplication

import db
from ui import MainWindow


def main():
    db.init_db()
    db.recover_if_crashed()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # keep alive when hidden to tray

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
