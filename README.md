# 📒 Adressbuch (GUI)

Ein einfaches, lokales Adressbuch mit grafischer Oberfläche (GUI) auf Basis von **Python 3** und **PySide6**.
Kontakte werden lokal in einer JSON-Datei gespeichert und können als **CSV** oder **vCard (VCF)** importiert sowie exportiert werden.

---

## 🚀 Funktionen

* Lokale Speicherung in `addressbook.json` (keine Cloud, keine fremden Server)
* GUI mit Listen- & Detailansicht
* CSV- und vCard-Import (automatische Feldzuordnung)
* CSV- und vCard-Export
* Kontakte anlegen, bearbeiten, löschen
* Schnellsuche nach Name/E-Mail
* `mailto:`- und Webseitenlinks direkt anklickbar

---

## 📦 Installation

### Voraussetzungen

* **Python 3.9+** empfohlen
* Abhängigkeit installieren:

```bash
pip install PySide6
```

---

## ▶️ Anwendung starten

```bash
python addressbook_gui.py
```

Die grafische Oberfläche startet automatisch.

---

## 📂 Datenablage

Beim ersten Start wird automatisch erzeugt:

```
./addressbook.json
```

Jeder Kontakt erhält eine interne ID. Beim Import werden bestehende Kontakte anhand der E-Mail aktualisiert, um Dubletten zu vermeiden.

---

## 📥 Import & 📤 Export

### **CSV Import**

* `;` oder `,` werden automatisch erkannt
* Flexible Spaltennamen-Unterstützung (z. B. `vorname`, `firstname`, `given_name`)

### **vCard Import**

* Unterstützt vCard v2.1/3.0
* Liest u. a.: Name, Telefon, Adresse, Geburtstag, Webseite

### **Dateiformate beim Export**

| Format | Standarddateiname |
| ------ | ----------------- |
| CSV    | `adressbuch.csv`  |
| vCard  | `adressbuch.vcf`  |

---

## 🧱 Projektstruktur

```
├── addressbook_gui.py   # GUI & Programmlogik
├── addressbook.json     # wird beim ersten Start erzeugt
└── README.md            # (diese Datei)
```

---

## 🔧 Weiterentwicklung (Ideen)

* Kategorien/Tags für Kontakte
* Geburtstags-Erinnerungen
* Synchronisation mit CardDAV/Nextcloud
* Mehrere Adressbücher verwalten
* Drag & Drop für vCards

---

## 📄 Lizenz

Dieses Projekt kann frei genutzt und erweitert werden.
Für öffentliche Projekte wird die **MIT-Lizenz** empfohlen.
