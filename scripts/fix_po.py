#!/usr/bin/env python
"""Fix format string and newline errors in translated .po files."""
import polib
import re

LANGUAGES = {
    'de': {
        'Seite %(Anzahl)s von %(Seiten)s': 'Seite %(number)s von %(pages)s',
        'Seite %(Anzahl)s von %(pages)s': 'Seite %(number)s von %(pages)s',
    },
    'fr': {
        'Page %(nombre)s de %(pages)s': 'Page %(number)s de %(pages)s',
    },
    'it': {
        # Italian missing format vars - fix by looking up msgid
    },
}

def fix_format_strings(po_path, replacements):
    po = polib.pofile(po_path)
    fixed = 0
    for entry in po:
        if entry.msgstr in replacements:
            entry.msgstr = replacements[entry.msgstr]
            fixed += 1
    po.save()
    return fixed

def fix_italian_format_vars(po_path):
    """Fix Italian format variable names that were translated."""
    po = polib.pofile(po_path)
    fixed = 0
    for entry in po:
        if entry.msgid and entry.msgstr:
            original = entry.msgstr
            # Fix %(grace)s -> should stay as %(grace)s  
            # Fix %(number)s -> should stay as %(number)s
            # Fix %(pages)s -> should stay as %(pages)s
            # Use regex to find all %(xxx)s patterns in msgid
            msgid_vars = set(re.findall(r'%\((\w+)\)s', entry.msgid))
            msgstr_vars = set(re.findall(r'%\((\w+)\)s', entry.msgstr))
            if msgid_vars and msgstr_vars != msgid_vars:
                # Some vars were translated - fix them
                new_msgstr = entry.msgstr
                for var in msgstr_vars - msgid_vars:
                    # This var name was translated, find the original
                    # For now, just replace back to msgid var
                    for orig_var in msgid_vars - msgstr_vars:
                        if var.lower() in orig_var.lower() or orig_var.lower() in var.lower():
                            new_msgstr = new_msgstr.replace(f'%({var})s', f'%({orig_var})s')
                            break
                if new_msgstr != entry.msgstr:
                    entry.msgstr = new_msgstr
                    fixed += 1
    po.save()
    return fixed

def fix_newline_mismatch(po_path):
    """Fix entries where msgid starts with \n but msgstr doesn't."""
    po = polib.pofile(po_path)
    fixed = 0
    for entry in po:
        if entry.msgid and entry.msgstr:
            if entry.msgid.startswith('\n') and not entry.msgstr.startswith('\n'):
                entry.msgstr = '\n' + entry.msgstr
                fixed += 1
    po.save()
    return fixed

def main():
    for lang, replacements in LANGUAGES.items():
        po_path = f'/app/locale/{lang}/LC_MESSAGES/django.po'
        f1 = fix_format_strings(po_path, replacements)
        f2 = fix_italian_format_vars(po_path)
        f3 = fix_newline_mismatch(po_path)
        print(f'{lang}: format_fix={f1}, it_fix={f2}, nl_fix={f3}')

if __name__ == '__main__':
    main()
