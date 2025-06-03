from pathlib import Path
from typing import List, Iterator
import polib
import langcodes


class LocaleFile:
    def __init__(self, path: Path):
        self.path = path
        self.filename = path.name
        self.entries = polib.pofile(str(path))
        self.modified = False

    def get(self, msgid: str) -> str | None:
        entry = self.entries.find(msgid)
        return entry.msgstr if entry else None

    def set(self, msgid: str, msgstr: str):
        entry = self.entries.find(msgid)
        if entry:
            entry.msgstr = msgstr
            self.modified = True

    def save(self):
        if self.modified:
            self.entries.save(str(self.path))
            self.modified = False

    def untranslated(self):
        return [
            entry for entry in self.entries
            if not entry.translated() or 'fuzzy' in entry.flags
        ]

    def __str__(self):
        return f"{self.filename} ({len(self.entries)} entries)"


class LocaleEntry:
    def __init__(self, path: Path):
        self.path = path
        self.language_code = path.name
        self.po_files = self._load_po_files()

    def _load_po_files(self) -> List[LocaleFile]:
        return [
            LocaleFile(f)
            for f in self.path.rglob("*.po")
            if f.is_file()
        ]

    def __iter__(self) -> Iterator[LocaleFile]:
        return iter(self.po_files)

    @property
    def language(self) -> str:
        try:
            return langcodes.get(self.language_code).language_name('ru')
        except Exception:
            return self.language_code

    @property
    def country(self) -> str:
        try:
            info = langcodes.get(self.language_code)
            region = info.region
            if region:
                return langcodes.get(region).territory_name('ru')
            return ""
        except Exception:
            return ""

    def __str__(self):
        return f"{self.language_code}: {[f.filename for f in self.po_files]} ({self.language})"


class LocaleManager:
    def __init__(self, locales_dir: str | Path):
        self.locales_path = Path(locales_dir)
        self.locales = self._discover_locales()

    def _discover_locales(self) -> List[LocaleEntry]:
        return [
            LocaleEntry(entry)
            for entry in self.locales_path.iterdir()
            if entry.is_dir()
        ]

    def get(self, lang_code: str) -> LocaleEntry | None:
        for locale in self.locales:
            if locale.language_code == lang_code:
                return locale
        return None

    def languages(self) -> List[str]:
        return [locale.language_code for locale in self.locales]

    def __iter__(self) -> Iterator[LocaleEntry]:
        return iter(self.locales)

    def __str__(self):
        return f"LocaleManager: {self.languages()}"