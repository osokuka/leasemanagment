#!/usr/bin/env python
"""Auto-populate translation files using Google Translate."""
import os
import sys
import time
import polib
from deep_translator import GoogleTranslator

LOCALE_DIR = '/app/locale'
TARGET_LANGS = {
    'de': 'de',
    'fr': 'fr',
    'it': 'it',
}

def translate_batch(texts, target_lang):
    """Translate a batch of texts."""
    results = []
    for text in texts:
        try:
            t = GoogleTranslator(source='en', target=target_lang)
            result = t.translate(text)
            results.append(result if result else text)
        except Exception as e:
            print(f"  ERROR: {text[:30]}... -> {e}", file=sys.stderr)
            results.append(text)
        time.sleep(0.2)
    return results

def populate_po_file(po_path, target_lang):
    """Populate empty msgstr fields in a .po file."""
    po = polib.pofile(po_path)
    empty_entries = []
    
    for i, entry in enumerate(po):
        if entry.msgid and not entry.msgstr:
            empty_entries.append((i, entry.msgid))
    
    if not empty_entries:
        print(f"  Already complete ({sum(1 for e in po if e.msgid and e.msgstr)} translations)")
        return 0
    
    print(f"  Found {len(empty_entries)} empty entries, translating...")
    
    filled = 0
    for idx, msgid in empty_entries:
        try:
            t = GoogleTranslator(source='en', target=target_lang)
            result = t.translate(msgid)
            if result:
                po[idx].msgstr = result
                filled += 1
            time.sleep(0.2)
        except Exception as e:
            print(f"  ERROR translating '{msgid[:40]}': {e}", file=sys.stderr)
    
    po.save()
    return filled

def main():
    for lang, gt_lang in TARGET_LANGS.items():
        po_path = os.path.join(LOCALE_DIR, lang, 'LC_MESSAGES', 'django.po')
        if not os.path.exists(po_path):
            print(f"SKIP: {lang} - file not found")
            continue
        
        print(f"\n{'='*50}")
        print(f"Translating to: {lang}")
        print(f"{'='*50}")
        
        filled = populate_po_file(po_path, gt_lang)
        print(f"  Result: {filled} entries filled")
        
        # Verify
        po = polib.pofile(po_path)
        count = sum(1 for e in po if e.msgid and e.msgstr)
        print(f"  Total translations: {count}")
        
        time.sleep(1)

if __name__ == '__main__':
    main()
