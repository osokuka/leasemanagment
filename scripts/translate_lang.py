#!/usr/bin/env python
"""Translate one language at a time."""
import sys
import time
import polib
from deep_translator import GoogleTranslator

target_lang = sys.argv[1]  # de, fr, or it
po_path = f'/app/locale/{target_lang}/LC_MESSAGES/django.po'

po = polib.pofile(po_path)
filled = 0
errors = 0

for i, entry in enumerate(po):
    if entry.msgid and not entry.msgstr:
        try:
            t = GoogleTranslator(source='en', target=target_lang)
            result = t.translate(entry.msgid)
            if result:
                po[i].msgstr = result
                filled += 1
            time.sleep(0.15)
        except Exception as e:
            errors += 1
            time.sleep(1)

po.save()
print(f'{target_lang}: filled={filled}, errors={errors}')
