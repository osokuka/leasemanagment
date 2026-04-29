#!/usr/bin/env python
"""Auto-populate translation files using Google Translate."""
import os
import time
import polib
from deep_translator import GoogleTranslator


LOCALE_DIR = '/app/locale'
LANGUAGES = ['de', 'fr', 'it']
SOURCE_LANG = 'sq'  # Use Albanian as reference since it's fully translated


def get_source_translations(locale_dir):
    """Read Albanian translations as reference (msgid -> translated_msgstr)."""
    sq_po = os.path.join(locale_dir, 'sq', 'LC_MESSAGES', 'django.po')
    sq = polib.pofile(sq_po)
    translations = {}
    for entry in sq:
        if entry.msgid and entry.msgstr:
            translations[entry.msgid] = entry.msgstr
    return translations


def translate_text(text, target_lang):
    """Translate text from English to target language."""
    try:
        translator = GoogleTranslator(source='en', target=target_lang)
        result = translator.translate(text)
        return result if result else text
    except Exception as e:
        print(f"  ERROR translating '{text[:40]}': {e}")
        return text


def populate_po_file(po_path, target_lang, source_translations):
    """Populate empty msgstr fields in a .po file."""
    po = polib.pofile(po_path)
    filled = 0
    skipped = 0
    errors = 0

    for entry in po:
        if entry.msgid and not entry.msgstr:
            # Try Albanian reference first
            if entry.msgid in source_translations:
                # Use Albanian as-is if it looks like a good translation
                sq_text = source_translations[entry.msgid]
                if sq_text and sq_text != entry.msgid:
                    entry.msgstr = sq_text
                    filled += 1
                    continue

            # Translate from English
            translated = translate_text(entry.msgid, target_lang)
            if translated:
                entry.msgstr = translated
                filled += 1
                time.sleep(0.3)  # Rate limit
            else:
                errors += 1
        elif entry.msgstr:
            skipped += 1

    return filled, skipped, errors


def main():
    source_translations = get_source_translations(LOCALE_DIR)
    print(f"Loaded {len(source_translations)} Albanian reference translations")

    for lang in LANGUAGES:
        po_path = os.path.join(LOCALE_DIR, lang, 'LC_MESSAGES', 'django.po')
        if not os.path.exists(po_path):
            print(f"SKIP: {lang} - file not found")
            continue

        print(f"\n{'='*50}")
        print(f"Translating: {lang}")
        print(f"{'='*50}")

        filled, skipped, errors = populate_po_file(po_path, lang, source_translations)
        print(f"  Filled: {filled}, Skipped (already filled): {skipped}, Errors: {errors}")

        # Save
        po = polib.pofile(po_path)
        po.metadata['Language'] = lang
        po.save()
        print(f"  Saved: {po_path}")

        time.sleep(1)


if __name__ == '__main__':
    main()
