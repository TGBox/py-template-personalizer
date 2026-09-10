# FastReport (.fr3) Template Personalizer

Ein Python-Programm zum automatischen Personalisieren von FastReport (`.fr3`) Druckvorlagen. Das Tool ersetzt relationale Datenbankreferenzen (wie `praxis.*`, `logo.*`) in Textfeldern, Attributen und PascalScript-Abschnitten durch vorkonfigurierte Werte und bereinigt überflüssige Live-Datenbindungen.

## Funktionen

- **Memo-Texte**: Ersetzt Platzhalter wie `[praxis."name"]`, `[praxis."strasse"]`, `[praxis."plz"] [praxis."ort"]` etc. durch konfigurierte Werte.
- **Datenbindungen**: Entfernt `DataSet`-, `DataSetName`- und `DataField`-Attribute an `TfrxMemoView`-Elementen, sobald alle referenzierten Felder statisch personalisiert wurden. Dadurch überschreibt die FastReport-Engine den statischen Text zur Laufzeit nicht mit leeren Werten.
- **PascalScript & Barcodes**: Ersetzt PascalScript-Ausdrücke wie `<praxis."bic">`, `<praxis."iban">` und `<logo."filename">` (z. B. in Bedingungen oder Barcode-Ausdrücken) durch valide Pascal-String-Literale (z. B. `'GENODEF1ULM'`).
- **Logo-Konfiguration**: Unterstützt das Personalisieren des Logos über `logo.filename`.
- **FastReport XML-Integrität**: Garantiert den Erhalt des originalen FastReport XML-Formats (inkl. `<?xml ... standalone="no"?>`, Attribut-Entities wie `&#13;&#10;`, `&#34;`, `&#60;`, `&#62;`).
- **Flexible Konfiguration**: Unterstützt YAML (`config.yaml`) und JSON (`config.json`).
- **CLI mit Vorschau & Scanner**:
  - `--dry-run`: Prüft alle Vorlagen und zeigt detaillierte Statistiken ohne Dateien zu ändern.
  - `--generate-config`: Durchsucht Vorlagen und erstellt automatisch eine Muster-Konfigurationsdatei.
  - `--output-dir` & `--in-place`: Wahl zwischen separatem Zielordner oder direktem Überschreiben.

---

## Installation

Benötigt Python 3.9+:

```bash
pip install -e .
```
Oder direkt Abhängigkeiten installieren:
```bash
pip install pyyaml pytest
```

---

## Verwendung

### 1. Konfiguration vorbereiten
Kopiere `config.example.yaml` nach `config.yaml` oder generiere eine leere Konfiguration direkt aus den Vorlagen:

```bash
python main.py --generate-config config.yaml
```

Beispiel `config.yaml`:
```yaml
praxis:
  name: "Praxis für Physiotherapie Mustermann"
  namenszusatz: "Gemeinschaftspraxis & Therapiezentrum"
  inhaber: "Dr. Max Mustermann"
  strasse: "Gesundheitsstraße 42"
  plz: "89073"
  ort: "Ulm"
  telefon1: "0731 / 123456"
  telefon2: "0171 / 9876543"
  email: "info@praxis-mustermann.de"
  website: "www.praxis-mustermann.de"
  unternehmen: "Praxis Mustermann GbR"
  bank: "Volksbank Ulm"
  iban: "DE02630901440012345678"
  bic: "GENODEF1ULM"
  steuerid: "DE987654321"

logo:
  filename: "praxis_logo.png"
```

### 2. Vorschau (Dry-Run)
Vorlagen prüfen und geplante Änderungen anzeigen:

```bash
python main.py --dry-run
```

### 3. Personalisieren (in Zielordner speichern)
Erstellt personalisierte Kopien im Ordner `output/`:

```bash
python main.py --input-dir testdata --output-dir output
```

### 4. Direkt im Quellordner überschreiben (In-Place)
```bash
python main.py --input-dir testdata --in-place
```

---

## Tests

Die Testsuite führt 22 Unit- und Integrationstests aus (inklusive Testlauf über alle 44 Vorlagen in `testdata`):

```bash
pytest -v
```
