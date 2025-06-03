# AutoPo
This application is designed to automatically translate .po files into various languages using OpenAI models

This application provides a small GUI for creating and editing `gettext`\
localization catalogs. It relies on **PyQt5**, **pybabel**, and the
modules in the `core/` package for translating strings with OpenAI.

## Usage

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the editor:
   ```bash
   python po_localizer_editor.py
   ```

   On start you can create a new localization catalog or open an
   existing one. New catalogs are created inside the selected directory
   in a `locales/` folder. After editing you can update and compile the
   catalog using the menu actions.

Environment variables required for translation are loaded from `.env`:
`OPENAI_API_KEY`, `MODEL` and `PROXY_URL`.