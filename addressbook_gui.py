#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import datetime
import csv
import uuid
from typing import Dict, List, Tuple, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QMessageBox, QDialog, QFormLayout, QLabel,
    QListWidget, QListWidgetItem, QSplitter, QFileDialog, QMenuBar
)
from PySide6.QtGui import QAction

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ADDRESSBOOK_PATH = os.path.join(BASE_DIR, "addressbook.json")

DEFAULT_CONTACT = {
    "_id": "",
    "vorname": "", "name": "", "strasse": "", "plz": "", "ort": "",
    "mobile": "", "festnetz": "", "email": "", "geburtsdatum": "",
    "webseite": "", "last_used": ""
}


# ------------------------------------------------------------
# Utilities (Import)
# ------------------------------------------------------------
def _safe_strip(v) -> str:
    return (v or "").strip()


def _unfold_vcard_lines(raw: str) -> List[str]:
    """RFC 2425/2426 line unfolding: lines starting with space/tab continue previous line."""
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    lines = raw.split("\n")
    out: List[str] = []
    for ln in lines:
        if not ln:
            out.append("")
            continue
        if (ln.startswith(" ") or ln.startswith("\t")) and out:
            out[-1] += ln[1:]
        else:
            out.append(ln)
    return out


def parse_vcard_contacts(text: str) -> List[Dict[str, str]]:
    """Very small vCard parser (good enough for common vCard 2.1/3.0 exports).
    Extracts: vorname, name, email, mobile, festnetz, strasse, plz, ort, webseite, geburtsdatum.
    """
    lines = _unfold_vcard_lines(text)
    contacts: List[Dict[str, str]] = []
    in_card = False
    cur: Dict[str, str] = {}

    def commit():
        nonlocal cur
        if cur:
            contacts.append({**DEFAULT_CONTACT, **cur})
        cur = {}

    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue

        up = ln.upper()
        if up == "BEGIN:VCARD":
            in_card = True
            cur = {}
            continue
        if up == "END:VCARD":
            if in_card:
                commit()
            in_card = False
            continue
        if not in_card:
            continue

        if ":" not in ln:
            continue

        left, value = ln.split(":", 1)
        left_up = left.upper()

        # Property name may include params: TEL;TYPE=CELL,VOICE
        prop = left_up.split(";", 1)[0]

        if prop == "N":
            # N:Nachname;Vorname;Weitere;Titel;Suffix
            parts = value.split(";")
            cur["name"] = _safe_strip(parts[0]) if len(parts) > 0 else ""
            cur["vorname"] = _safe_strip(parts[1]) if len(parts) > 1 else cur.get("vorname", "")
        elif prop == "FN":
            # Full name (fallback if N missing)
            if not cur.get("name") and value.strip():
                # try split last token as last name
                bits = value.strip().split()
                if len(bits) == 1:
                    cur["name"] = bits[0]
                else:
                    cur["vorname"] = " ".join(bits[:-1])
                    cur["name"] = bits[-1]
        elif prop == "EMAIL":
            if not cur.get("email"):
                cur["email"] = _safe_strip(value).lower()
        elif prop == "TEL":
            params = left_up.split(";", 1)[1] if ";" in left_up else ""
            p = params.replace("TYPE=", "")
            p = p.replace(",", ";")
            pset = {x.strip() for x in p.split(";") if x.strip()}
            tel = _safe_strip(value)
            if not tel:
                continue
            if ("CELL" in pset) or ("MOBILE" in pset):
                if not cur.get("mobile"):
                    cur["mobile"] = tel
            elif ("HOME" in pset) or ("VOICE" in pset):
                if not cur.get("festnetz"):
                    cur["festnetz"] = tel
            else:
                # store first number as festnetz if empty, else mobile if empty
                if not cur.get("festnetz"):
                    cur["festnetz"] = tel
                elif not cur.get("mobile"):
                    cur["mobile"] = tel
        elif prop == "ADR":
            # ADR;TYPE=HOME:;;Street;City;Region;PostalCode;Country
            parts = value.split(";")
            if len(parts) >= 3 and not cur.get("strasse"):
                cur["strasse"] = _safe_strip(parts[2])
            if len(parts) >= 6:
                if not cur.get("ort"):
                    cur["ort"] = _safe_strip(parts[3])
                if not cur.get("plz"):
                    cur["plz"] = _safe_strip(parts[5])
        elif prop in ("URL", "WEB", "WEBSITE"):
            if not cur.get("webseite"):
                cur["webseite"] = _safe_strip(value)
        elif prop in ("BDAY", "BIRTHDAY"):
            if not cur.get("geburtsdatum"):
                cur["geburtsdatum"] = _safe_strip(value)
        # else: ignore

    # In case file ends without END:VCARD
    if in_card and cur:
        commit()

    return contacts


# ------------------------------------------------------------
# Datenmodell
# ------------------------------------------------------------
class AddressBook:
    def __init__(self, path: str):
        self.path = path
        self._data = {"contacts": []}
        self.load()

    def load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                if "contacts" not in self._data or not isinstance(self._data.get("contacts"), list):
                    self._data = {"contacts": []}
            except Exception:
                self._data = {"contacts": []}

        # ensure every contact has a stable internal id
        for c in self._data.get("contacts", []):
            if isinstance(c, dict) and not c.get("_id"):
                c["_id"] = uuid.uuid4().hex
        # persist upgraded structure
        self.save()

    def save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def all_contacts(self):
        return list(self._data.get("contacts", []))


    def find_by_id(self, cid: str):
        cid = (cid or "").strip()
        for c in self._data.get("contacts", []):
            if (c.get("_id") or "").strip() == cid:
                return c
        return None

    def find_by_email(self, email: str):
        email = (email or "").lower().strip()
        for c in self._data["contacts"]:
            if (c.get("email") or "").lower().strip() == email:
                return c
        return None

    def upsert_full(self, contact: dict):
        # Merge contact into address book.
        # 1) If _id exists -> update that record
        # 2) Else if email exists -> update matching email (keep its _id)
        # 3) Else -> create new record
        if not isinstance(contact, dict):
            return

        incoming = {**DEFAULT_CONTACT, **contact}

        cid = (incoming.get("_id") or "").strip()
        if cid:
            existing = self.find_by_id(cid)
            if existing is not None:
                existing.update(incoming)
                self.save()
                return

        email = (incoming.get("email") or "").strip()
        if email:
            existing = self.find_by_email(email)
            if existing is not None:
                incoming["_id"] = existing.get("_id") or uuid.uuid4().hex
                existing.update(incoming)
                self.save()
                return

        incoming["_id"] = uuid.uuid4().hex
        self._data.setdefault("contacts", []).append(incoming)
        self.save()

    def delete_by_id(self, cid: str):
        cid = (cid or "").strip()
        self._data["contacts"] = [
            c for c in self._data.get("contacts", [])
            if (c.get("_id") or "").strip() != cid
        ]
        self.save()

    # Backward compatible helper
    def delete_by_email(self, email: str):
        c = self.find_by_email(email)
        if c and c.get("_id"):
            self.delete_by_id(c["_id"])



# ------------------------------------------------------------
# Kontakt-Dialog
# ------------------------------------------------------------
class ContactEditDialog(QDialog):
    def __init__(self, parent=None, contact=None):
        super().__init__(parent)
        self.setWindowTitle("Kontakt")
        self.resize(520, 420)

        c = {**DEFAULT_CONTACT, **(contact or {})}

        self._id = c.get("_id", "")

        self.ed_vorname = QLineEdit(c["vorname"])
        self.ed_name = QLineEdit(c["name"])
        self.ed_strasse = QLineEdit(c["strasse"])
        self.ed_plz = QLineEdit(c["plz"])
        self.ed_ort = QLineEdit(c["ort"])
        self.ed_mobile = QLineEdit(c["mobile"])
        self.ed_festnetz = QLineEdit(c["festnetz"])
        self.ed_email = QLineEdit(c["email"])
        self.ed_geb = QLineEdit(c["geburtsdatum"])
        self.ed_web = QLineEdit(c["webseite"])

        form = QFormLayout()
        form.addRow("Vorname:", self.ed_vorname)
        form.addRow("Name:", self.ed_name)
        form.addRow("Straße:", self.ed_strasse)
        form.addRow("PLZ:", self.ed_plz)
        form.addRow("Ort:", self.ed_ort)
        form.addRow("Mobile:", self.ed_mobile)
        form.addRow("Festnetz:", self.ed_festnetz)
        form.addRow("E-Mail:", self.ed_email)
        form.addRow("Geburtsdatum:", self.ed_geb)
        form.addRow("Webseite:", self.ed_web)

        btn_ok = QPushButton("Speichern")
        btn_cancel = QPushButton("Abbrechen")
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)

        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(btn_ok)
        row.addWidget(btn_cancel)

        root = QVBoxLayout()
        root.addLayout(form)
        root.addLayout(row)
        self.setLayout(root)

    def get_contact(self):
        return {
            "_id": self._id,
            "vorname": self.ed_vorname.text().strip(),
            "name": self.ed_name.text().strip(),
            "strasse": self.ed_strasse.text().strip(),
            "plz": self.ed_plz.text().strip(),
            "ort": self.ed_ort.text().strip(),
            "mobile": self.ed_mobile.text().strip(),
            "festnetz": self.ed_festnetz.text().strip(),
            "email": self.ed_email.text().strip(),
            "geburtsdatum": self.ed_geb.text().strip(),
            "webseite": self.ed_web.text().strip(),
        }


# ------------------------------------------------------------
# Hauptfenster (Thunderbird-Stil)
# ------------------------------------------------------------
class AddressBookWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Adressbuch")
        self.resize(1000, 560)
        self.abook = AddressBook(ADDRESSBOOK_PATH)

        # Menü
        menubar = QMenuBar(self)
        self.setMenuBar(menubar)
        m_file = menubar.addMenu("Datei")

        act_import_csv = QAction("Import CSV…", self)
        act_import_vcf = QAction("Import vCard…", self)
        act_csv = QAction("Export CSV…", self)
        act_vcf = QAction("Export vCard…", self)

        m_file.addAction(act_import_csv)
        m_file.addAction(act_import_vcf)
        m_file.addSeparator()
        m_file.addAction(act_csv)
        m_file.addAction(act_vcf)

        act_import_csv.triggered.connect(self.import_csv)
        act_import_vcf.triggered.connect(self.import_vcard)
        act_csv.triggered.connect(self.export_csv)
        act_vcf.triggered.connect(self.export_vcard)

        # Suche / Buttons
        self.search = QLineEdit()
        self.search.setPlaceholderText("Suchen (Name oder E-Mail)…")

        btn_new = QPushButton("Neu…")
        btn_edit = QPushButton("Bearbeiten…")
        btn_del = QPushButton("Löschen")
        btn_reload = QPushButton("Aktualisieren")

        top = QHBoxLayout()
        top.addWidget(self.search, 1)
        top.addWidget(btn_new)
        top.addWidget(btn_edit)
        top.addWidget(btn_del)
        top.addWidget(btn_reload)

        # Liste links
        self.list = QListWidget()
        self.list.setMinimumWidth(320)

        # Details rechts
        self.lb_name = QLabel()
        self.lb_name.setStyleSheet("font-size:18px;font-weight:600")

        def val():
            l = QLabel()
            l.setTextInteractionFlags(Qt.TextSelectableByMouse)
            l.setWordWrap(True)
            return l

        self.v_strasse = val()
        self.v_plzort = val()
        self.v_mobile = val()
        self.v_festnetz = val()
        self.v_email = QLabel()
        self.v_email.setOpenExternalLinks(True)
        self.v_geb = val()
        self.v_web = QLabel()
        self.v_web.setOpenExternalLinks(True)

        form = QFormLayout()
        form.addRow("Straße:", self.v_strasse)
        form.addRow("PLZ / Ort:", self.v_plzort)
        form.addRow("Mobile:", self.v_mobile)
        form.addRow("Festnetz:", self.v_festnetz)
        form.addRow("E-Mail:", self.v_email)
        form.addRow("Geburtsdatum:", self.v_geb)
        form.addRow("Webseite:", self.v_web)

        details = QWidget()
        dlay = QVBoxLayout()
        dlay.addWidget(self.lb_name)
        dlay.addLayout(form)
        dlay.addStretch(1)
        details.setLayout(dlay)

        splitter = QSplitter()
        splitter.addWidget(self.list)
        splitter.addWidget(details)
        splitter.setStretchFactor(1, 1)

        root = QWidget()
        lay = QVBoxLayout()
        lay.addLayout(top)
        lay.addWidget(splitter, 1)
        root.setLayout(lay)
        self.setCentralWidget(root)

        # Signals
        self.search.textChanged.connect(self.reload)
        btn_reload.clicked.connect(self.reload)
        btn_new.clicked.connect(self.new_contact)
        btn_edit.clicked.connect(self.edit_selected)
        btn_del.clicked.connect(self.delete_selected)
        self.list.currentItemChanged.connect(self.on_select)

        self.reload()

    # --------------------------------------------------------

    def reload(self):
        self.abook.load()
        q = self.search.text().lower().strip()

        self.list.clear()
        rows = []

        for c in self.abook.all_contacts():
            name = (c.get("vorname", "") + " " + c.get("name", "")).lower()
            mail = (c.get("email", "") or "").lower()
            if not q or q in name or q in mail:
                rows.append(c)

        rows.sort(key=lambda c: (c.get("last_used") or ""), reverse=True)

        for c in rows:
            vor = c.get("vorname", "").strip()
            nam = c.get("name", "").strip()
            email = c.get("email", "").strip()
            full = (vor + " " + nam).strip()

            if full and email:
                text = f"{full}  <{email}>"
            elif full:
                text = full
            else:
                text = email or "(ohne Namen)"

            it = QListWidgetItem(text)
            it.setData(Qt.UserRole, c.get("_id", ""))
            self.list.addItem(it)

        if self.list.count():
            self.list.setCurrentRow(0)
        else:
            self.clear_details()

    def on_select(self, current, _):
        if not current:
            self.clear_details()
            return
        cid = current.data(Qt.UserRole)
        self.show_contact(self.abook.find_by_id(cid))

    def clear_details(self):
        self.lb_name.setText("")
        self.v_strasse.setText("")
        self.v_plzort.setText("")
        self.v_mobile.setText("")
        self.v_festnetz.setText("")
        self.v_email.setText("")
        self.v_geb.setText("")
        self.v_web.setText("")

    def show_contact(self, c):
        if not c:
            self.clear_details()
            return

        name = (c.get("vorname", "") + " " + c.get("name", "")).strip()
        email = c.get("email", "")

        self.lb_name.setText(name or email or "(ohne Namen)")
        self.v_strasse.setText(c.get("strasse", ""))
        self.v_plzort.setText((c.get("plz", "") + " " + c.get("ort", "")).strip())
        self.v_mobile.setText(c.get("mobile", ""))
        self.v_festnetz.setText(c.get("festnetz", ""))
        self.v_email.setText(f'<a href="mailto:{email}">{email}</a>' if email else "")
        self.v_geb.setText(c.get("geburtsdatum", ""))

        web = c.get("webseite", "")
        if web:
            if not web.startswith("http"):
                web = "https://" + web
            self.v_web.setText(f'<a href="{web}">{web}</a>')
        else:
            self.v_web.setText("")

    # --------------------------------------------------------

    def new_contact(self):
        dlg = ContactEditDialog(self)
        if dlg.exec():
            self.abook.upsert_full(dlg.get_contact())
            self.reload()

    def edit_selected(self):
        it = self.list.currentItem()
        if not it:
            return
        c = self.abook.find_by_id(it.data(Qt.UserRole))
        dlg = ContactEditDialog(self, c)
        if dlg.exec():
            self.abook.upsert_full(dlg.get_contact())
            self.reload()

    def delete_selected(self):
        it = self.list.currentItem()
        if not it:
            return
        if QMessageBox.question(self, "Löschen", "Kontakt löschen?") == QMessageBox.Yes:
            self.abook.delete_by_id(it.data(Qt.UserRole))
            self.reload()

    # --------------------------------------------------------
    # Import
    # --------------------------------------------------------
    def _import_contacts(self, contacts: List[Dict[str, str]], source_label: str):
            added = 0
            updated = 0
            skipped = 0
            errors: List[str] = []
    
            for c in contacts:
                try:
                    email = _safe_strip(c.get("email")).lower()
    
                    # If an email exists, we can treat it as a stable key for "update vs new".
                    exists = self.abook.find_by_email(email) if email else None
    
                    # Always import the contact, even without email.
                    self.abook.upsert_full(c)
    
                    if exists:
                        updated += 1
                    else:
                        added += 1
                except Exception as e:
                    skipped += 1
                    label = (
                        _safe_strip(c.get("email"))
                        or (_safe_strip(c.get("vorname")) + " " + _safe_strip(c.get("name"))).strip()
                        or "(unbekannt)"
                    )
                    errors.append(f"{label}: {e}")
    
            self.reload()
    
            # Ergebnis anzeigen
            if errors:
                error_text = "\n".join(errors[:10])
                QMessageBox.warning(
                    self,
                    "Import mit Warnungen",
                    f"{source_label} Import abgeschlossen.\n\n"
                    f"Neu: {added}\n"
                    f"Aktualisiert: {updated}\n"
                    f"Übersprungen: {skipped}\n\n"
                    f"Fehler (erste 10):\n{error_text}"
                )
            else:
                QMessageBox.information(
                    self,
                    "Import abgeschlossen",
                    f"{source_label} Import abgeschlossen.\n\n"
                    f"Neu: {added}\n"
                    f"Aktualisiert: {updated}\n"
                    f"Übersprungen: {skipped}"
                )

    def import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "CSV Import", "", "CSV (*.csv);;Alle Dateien (*.*)")
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8-sig", newline="") as f:
                # Heuristik: zuerst ; dann ,
                sample = f.read(2048)
                f.seek(0)
                delimiter = ";" if sample.count(";") >= sample.count(",") else ","
                reader = csv.DictReader(f, delimiter=delimiter)
                if not reader.fieldnames:
                    raise ValueError("Keine Header-Zeile gefunden.")

                # unterstützte Header (case-insensitive)
                norm = {h.strip().lower(): h for h in reader.fieldnames}

                def pick(*names) -> Optional[str]:
                    for n in names:
                        if n in norm:
                            return norm[n]
                    return None

                mapping = {
                    "vorname": pick("vorname", "firstname", "first_name", "givenname", "given_name"),
                    "name": pick("name", "nachname", "lastname", "last_name", "surname", "familyname", "family_name"),
                    "strasse": pick("strasse", "straße", "street", "address", "addr"),
                    "plz": pick("plz", "zip", "postal", "postalcode", "postal_code"),
                    "ort": pick("ort", "city", "town"),
                    "mobile": pick("mobile", "handy", "cell", "cellphone", "cell_phone"),
                    "festnetz": pick("festnetz", "phone", "tel", "telephone", "homephone", "home_phone"),
                    "email": pick("email", "e-mail", "mail"),
                    "geburtsdatum": pick("geburtsdatum", "birthday", "bday", "birthdate", "birth_date"),
                    "webseite": pick("webseite", "website", "url", "web"),
                }

                contacts: List[Dict[str, str]] = []
                for row in reader:
                    c = {}
                    for key, src in mapping.items():
                        if src:
                            c[key] = _safe_strip(row.get(src))
                    if c:
                        contacts.append(c)

        except Exception as e:
            QMessageBox.critical(self, "CSV Import", f"Konnte CSV nicht importieren:\n{e}")
            return

        self._import_contacts(contacts, "CSV")

    def import_vcard(self):
        path, _ = QFileDialog.getOpenFileName(self, "vCard Import", "", "vCard (*.vcf *.vcard);;Alle Dateien (*.*)")
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                text = f.read()
            contacts = parse_vcard_contacts(text)
        except Exception as e:
            QMessageBox.critical(self, "vCard Import", f"Konnte vCard nicht importieren:\n{e}")
            return

        self._import_contacts(contacts, "vCard")

    # --------------------------------------------------------
    # Export
    # --------------------------------------------------------
    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "CSV Export", "adressbuch.csv", "CSV (*.csv)")
        if not path:
            return
        fields = ["vorname", "name", "strasse", "plz", "ort", "mobile", "festnetz", "email", "geburtsdatum", "webseite"]
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields, delimiter=";")
            w.writeheader()
            for c in self.abook.all_contacts():
                w.writerow({k: c.get(k, "") for k in fields})

        QMessageBox.information(self, "Export", "CSV Export abgeschlossen.")

    def export_vcard(self):
        path, _ = QFileDialog.getSaveFileName(self, "vCard Export", "adressbuch.vcf", "vCard (*.vcf)")
        if not path:
            return

        with open(path, "w", encoding="utf-8") as f:
            for c in self.abook.all_contacts():
                f.write("BEGIN:VCARD\nVERSION:3.0\n")
                f.write(f"N:{c.get('name', '')};{c.get('vorname', '')};;;\n")
                f.write(f"FN:{(c.get('vorname', '') + ' ' + c.get('name', '')).strip()}\n")
                if c.get("email"):
                    f.write(f"EMAIL:{c['email']}\n")
                if c.get("mobile"):
                    f.write(f"TEL;TYPE=CELL:{c['mobile']}\n")
                if c.get("festnetz"):
                    f.write(f"TEL;TYPE=HOME:{c['festnetz']}\n")
                # Basic address (optional)
                if c.get("strasse") or c.get("ort") or c.get("plz"):
                    f.write(f"ADR;TYPE=HOME:;;{c.get('strasse','')};{c.get('ort','')};;{c.get('plz','')};;\n")
                if c.get("webseite"):
                    web = c.get("webseite", "")
                    if web and not web.startswith("http"):
                        web = "https://" + web
                    f.write(f"URL:{web}\n")
                if c.get("geburtsdatum"):
                    f.write(f"BDAY:{c.get('geburtsdatum')}\n")
                f.write("END:VCARD\n")

        QMessageBox.information(self, "Export", "vCard Export abgeschlossen.")


# ------------------------------------------------------------
def main():
    app = QApplication([])
    w = AddressBookWindow()
    w.show()
    app.exec()


if __name__ == "__main__":
    main()
