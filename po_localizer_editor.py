import sys
import subprocess
import shutil
from pathlib import Path
from typing import List, Optional

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QTableWidget, QTableWidgetItem, QAction, QFileDialog,
    QMessageBox, QHeaderView, QLineEdit, QLabel, QProgressDialog,
    QPushButton, QDialog, QDialogButtonBox, QCheckBox, QScrollArea,
    QGroupBox, QFormLayout
)
from PyQt5.QtCore import Qt

import polib
import langcodes
from babel import localedata

try:
    from core import translate
except ImportError:
    from translator import translate


def lang_display(code: str, ref: str = "ru") -> str:
    try:
        return f"{langcodes.get(code).language_name(ref).capitalize()} ({code})"
    except Exception:
        return code


class StartupDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Локализация: выбор режима")
        self.resize(400, 200)

        v = QVBoxLayout(self)
        v.addWidget(QLabel("Выберите действие:"))
        new_btn = QPushButton("Создать новую локализацию")
        open_btn = QPushButton("Открыть существующую локализацию")
        v.addWidget(new_btn)
        v.addWidget(open_btn)
        new_btn.clicked.connect(self.new)
        open_btn.clicked.connect(self.open)

        self.selected_path: Optional[Path] = None
        self.selected_langs: Optional[List[str]] = None

    def new(self):
        dlg = NewLocalizationDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            self.selected_path, self.selected_langs = dlg.target_path, dlg.selected_langs
            self.accept()

    def open(self):
        path = QFileDialog.getExistingDirectory(self, "Выберите папку с локализацией")
        if path:
            self.selected_path = Path(path)
            self.accept()


class NewLocalizationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Новая локализация")
        self.resize(600, 500)

        self.target_path: Optional[Path] = None
        self.selected_langs: List[str] = []
        self.checks: List[QCheckBox] = []

        main = QVBoxLayout(self)

        form = QFormLayout()
        self.path_lbl = QLabel("Не выбрана")
        choose_btn = QPushButton("Выбрать папку…")
        choose_btn.clicked.connect(self.choose_folder)
        form.addRow("Папка для локализации:", choose_btn)
        form.addRow("Текущая:", self.path_lbl)
        main.addLayout(form)

        self.search_edit = QLineEdit(placeholderText="Поиск языка (название или код)…")
        self.search_edit.textChanged.connect(self.filter_langs)
        main.addWidget(self.search_edit)

        group = QGroupBox("Выберите языки (≥2)")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        box = QWidget()
        box_layout = QVBoxLayout(box)

        codes = sorted({c.split('_')[0] for c in localedata.locale_identifiers()})
        for code in codes:
            cb = QCheckBox(lang_display(code))
            cb.setProperty("code", code)
            box_layout.addWidget(cb)
            self.checks.append(cb)

        scroll.setWidget(box)
        g_layout = QVBoxLayout(group)
        g_layout.addWidget(scroll)
        main.addWidget(group)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.on_ok)
        btns.rejected.connect(self.reject)
        main.addWidget(btns)

    def choose_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Выберите папку")
        if path:
            self.target_path = Path(path)
            self.path_lbl.setText(path)

    def filter_langs(self, text: str):
        q = text.lower().strip()
        for cb in self.checks:
            name = cb.text().lower()
            code = cb.property("code")
            cb.setVisible(not q or q in name or q in code.lower())

    def on_ok(self):
        if not self.target_path:
            QMessageBox.warning(self, "Ошибка", "Укажите папку.")
            return
        langs = [cb.property("code") for cb in self.checks if cb.isChecked()]
        if len(langs) < 2:
            QMessageBox.warning(self, "Ошибка", "Нужно выбрать минимум 2 языка.")
            return
        self.selected_langs = langs

        loc_dir = self.target_path / "locales"
        loc_dir.mkdir(exist_ok=True)
        pot = loc_dir / "messages.pot"
        subprocess.run(["pybabel", "extract", "--input-dirs=.", "-o", str(pot)])
        for l in langs:
            subprocess.run(["pybabel", "init", "-i", str(pot), "-d", str(loc_dir), "-D", "messages", "-l", l])
        self.accept()


class PoEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PO File Editor")
        self.resize(1000, 700)
        self.locales_dir: Optional[Path] = None
        self.languages: List[str] = []
        self.po_files = {}
        self.entries = []
        self.language_names: dict[str, str] = {}

        m = self.menuBar()
        f = m.addMenu("Файл")
        f.addAction("Выбрать каталог", self.select_locales)
        f.addAction("Сохранить", self.save_all)
        f.addSeparator()
        f.addAction("Выход", self.close)
        b = m.addMenu("Babel")
        b.addAction("Обновить каталог", self.refresh_catalog)
        b.addAction("Компилировать", self.compile_catalog)
        t = m.addMenu("Перевод")
        t.addAction("Перевести выделенный", self.auto_translate_current)
        t.addAction("Перевести всё", self.auto_translate_all)

        central = QWidget()
        self.setCentralWidget(central)
        main = QVBoxLayout(central)
        self.path_lbl = QLabel("Каталог: не выбран")
        main.addWidget(self.path_lbl)
        split = QHBoxLayout()
        main.addLayout(split)

        left = QVBoxLayout()
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self.show_trans)
        left.addWidget(self.list)
        self.edit_id = QLineEdit()
        self.edit_id.setEnabled(False)
        self.edit_id.returnPressed.connect(self.rename_msgid)
        left.addWidget(self.edit_id)
        split.addLayout(left, 2)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Язык", "Перевод"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        split.addWidget(self.table, 5)
        self.statusBar().showMessage("Готово")

    def select_locales(self):
        path = QFileDialog.getExistingDirectory(self, "Каталог locales")
        if path:
            self.locales_dir = Path(path)
            self.path_lbl.setText(f"Каталог: {path}")
            self.load()

    def load(self):
        if not (self.locales_dir and self.locales_dir.is_dir()):
            QMessageBox.warning(self, "Ошибка", "Каталог не найден")
            return
        self.languages.clear()
        self.po_files.clear()
        self.list.clear()
        self.table.setRowCount(0)
        for d in self.locales_dir.iterdir():
            po = d / "LC_MESSAGES" / "messages.po"
            if po.exists():
                self.languages.append(d.name)
                self.po_files[d.name] = polib.pofile(str(po))
        if not self.languages:
            QMessageBox.information(self, "Пусто", "Нет .po файлов")
            return
        ref = self.languages[0]
        self.language_names = {l: lang_display(l, ref) for l in self.languages}
        self.entries = [e.msgid for e in self.po_files[ref]]
        self.list.addItems(self.entries)
        self.statusBar().showMessage("Каталог загружен", 3000)

    def show_trans(self, row: int):
        if row < 0 or row >= len(self.entries):
            self.table.setRowCount(0)
            self.edit_id.clear()
            self.edit_id.setEnabled(False)
            return
        msgid = self.entries[row]
        self.edit_id.setEnabled(True)
        self.edit_id.setText(msgid)
        self.table.setRowCount(0)
        for i, lang in enumerate(self.languages):
            entry = self.po_files[lang].find(msgid)
            self.table.insertRow(i)
            lang_item = QTableWidgetItem(self.language_names[lang])
            lang_item.setFlags(lang_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(i, 0, lang_item)
            txt = entry.msgstr if entry else ""
            txt_item = QTableWidgetItem(txt)
            txt_item.setFlags(txt_item.flags() | Qt.ItemIsEditable)
            self.table.setItem(i, 1, txt_item)

    def rename_msgid(self):
        row = self.list.currentRow()
        old = self.entries[row] if row >= 0 else None
        new = self.edit_id.text().strip()
        if not old or not new or new == old or new in self.entries:
            return
        for po in self.po_files.values():
            e = po.find(old)
            if e:
                e.msgid = new
        self.entries[row] = new
        self.list.item(row).setText(new)
        self.statusBar().showMessage("msgid переименован", 3000)

    def _write_to_po(self, msgid: str):
        for r in range(self.table.rowCount()):
            lang = self.languages[r]
            text = self.table.item(r, 1).text()
            e = self.po_files[lang].find(msgid)
            if e and e.msgstr != text:
                e.msgstr = text

    def save_all(self):
        if not self.po_files:
            return
        cur = self.list.currentRow()
        if cur >= 0:
            self._write_to_po(self.entries[cur])
        for po in self.po_files.values():
            po.save()
        self.statusBar().showMessage("Сохранено", 3000)

    def refresh_catalog(self):
        if not self.locales_dir:
            QMessageBox.warning(self, "Ошибка", "Каталог не выбран")
            return
        self.save_all()
        base = self.locales_dir.parent
        pot = self.locales_dir / "messages.pot"
        subprocess.run(["pybabel", "extract", "--input-dirs=.", "-o", str(pot)], cwd=base)
        subprocess.run([
            "pybabel", "extract", "-k", "_:1,1t", "-k", "_:1,2", "-k", "__",
            "--input-dirs=.", "-o", str(pot)
        ], cwd=base)
        subprocess.run([
            "pybabel", "update", "-d", str(self.locales_dir), "-D", "messages",
            "-i", str(pot)
        ], cwd=base)
        msgattrib = shutil.which("msgattrib")
        for d in self.locales_dir.iterdir():
            po = d / "LC_MESSAGES" / "messages.po"
            if not po.exists():
                continue
            if msgattrib:
                subprocess.run([msgattrib, "--no-obsolete", "-o", str(po), str(po)])
            else:
                p = polib.pofile(str(po))
                for e in p.obsolete_entries():
                    p.remove(e)
                p.save()
        self.load()
        self.statusBar().showMessage("Каталог обновлён", 3000)

    def compile_catalog(self):
        if not self.locales_dir:
            QMessageBox.warning(self, "Ошибка", "Каталог не выбран")
            return
        self.save_all()
        base = self.locales_dir.parent
        subprocess.run(["pybabel", "compile", "-d", str(self.locales_dir), "-D", "messages"], cwd=base)
        self.statusBar().showMessage("Каталог скомпилирован", 3000)

    def _translate(self, msgid: str, langs: List[str]):
        if not langs:
            return
        try:
            res = translate(msgid, langs)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка API", str(e))
            return
        for tr in res.translations:
            po = self.po_files.get(tr.language)
            if po:
                e = po.find(msgid)
                if e:
                    e.msgstr = tr.translate
                else:
                    po.append(polib.POEntry(msgid=msgid, msgstr=tr.translate))

    def auto_translate_current(self):
        row = self.list.currentRow()
        if row < 0:
            return
        msgid = self.entries[row]
        missing = [
            l for l in self.languages
            if not (self.po_files[l].find(msgid) and self.po_files[l].find(msgid).msgstr.strip())
        ]
        if not missing:
            self.statusBar().showMessage("Перевод не нужен", 3000)
            return
        self._translate(msgid, missing)
        self.show_trans(row)
        self.statusBar().showMessage("Переведено", 3000)

    def auto_translate_all(self):
        if not self.entries:
            return
        dlg = QProgressDialog("Автоперевод…", "Отмена", 0, len(self.entries), self)
        dlg.setWindowModality(Qt.WindowModal)
        for i, msgid in enumerate(self.entries):
            if dlg.wasCanceled():
                break
            miss = [
                l for l in self.languages
                if not (self.po_files[l].find(msgid) and self.po_files[l].find(msgid).msgstr.strip())
            ]
            self._translate(msgid, miss)
            dlg.setValue(i + 1)
        dlg.close()
        self.show_trans(self.list.currentRow())
        self.statusBar().showMessage("Автоперевод завершён", 3000)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    st = StartupDialog()
    if st.exec_() == QDialog.Accepted:
        loc_root = (st.selected_path / "locales") if st.selected_langs else st.selected_path
        ed = PoEditor()
        ed.locales_dir = loc_root
        ed.load()
        ed.show()
        sys.exit(app.exec_())