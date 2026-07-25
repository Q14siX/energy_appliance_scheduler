<p align="center">
  <img src="https://raw.githubusercontent.com/Q14siX/energy_appliance_scheduler/main/custom_components/energy_appliance_scheduler/brand/logo.png" alt="Energy Appliance Scheduler" width="760">
</p>

# Energy Appliance Scheduler

**Energy Appliance Scheduler** ist eine native Home-Assistant-Integration zur zeit- und strompreisabhängigen Steuerung von Waschmaschinen, Trocknern, Geschirrspülern und weiteren Geräten. Sie nutzt die von `energy_storage_control` bereitgestellten Günstigphasen und Strompreise und verwaltet mehrere Geräte innerhalb eines einzigen Integrationseintrags.

Die Integration legt **keine `input_boolean`-, `input_select`-, `input_datetime`- oder sonstigen Helfer** an. Alle Bedienelemente werden als native Home-Assistant-Entitäten erzeugt.

## GitHub-Repository

Repository:

```text
https://github.com/Q14siX/energy_appliance_scheduler
```

Kurze GitHub-Beschreibung:

> Home-Assistant-Integration zur zeit- und strompreisabhängigen Steuerung von Waschmaschine, Trockner, Geschirrspüler und weiteren Geräten. Unterstützt Günstigphasen, feste Startzeiten, Programmauswahl, Alexa-Ansagen und mehrere Geräte in einer einzigen Integration.

## Voraussetzungen und verwendete Projekte

- [Home Assistant](https://www.home-assistant.io/) **2026.7 oder neuer**
- [HACS](https://github.com/hacs/integration) für die empfohlene Installation und Aktualisierung
- zwingend erforderlich: [Energy Storage Control](https://github.com/Q14siX/energy_storage_control) von **Q14siX**, installiert und vollständig eingerichtet
- folgende Entitäten aus **Energy Storage Control**:
  - `sensor.esc_…_favorable_phase`
  - `binary_sensor.esc_…_favorable_now`
  - `sensor.esc_…_current_price`
- für Sprachausgaben optional: [Alexa Media Player](https://github.com/alandtse/alexa_media_player) (`alexa_media`), installiert und eingerichtet
- bei Geräten aus dem Home-Connect-Ökosystem optional: die in Home Assistant enthaltene [Home-Connect-Integration](https://www.home-assistant.io/integrations/home_connect/)

**Energy Appliance Scheduler ist ohne Energy Storage Control nicht funktionsfähig**, da die Günstigphasen und Strompreisdaten von dieser Integration bereitgestellt werden.

## Installation über HACS

Die empfohlene Installation und Aktualisierung erfolgt über [HACS](https://github.com/hacs/integration). Vor der Einrichtung von Energy Appliance Scheduler muss außerdem [Energy Storage Control](https://github.com/Q14siX/energy_storage_control) installiert und vollständig eingerichtet sein.

### Repository als benutzerdefiniertes Repository hinzufügen

1. HACS in Home Assistant öffnen.
2. **Integrationen** auswählen.
3. Oben rechts das Drei-Punkte-Menü öffnen.
4. **Benutzerdefinierte Repositories** auswählen.
5. Folgende Repository-URL eintragen:

   ```text
   https://github.com/Q14siX/energy_appliance_scheduler
   ```

6. Als Kategorie **Integration** auswählen.
7. Das Repository hinzufügen.
8. In HACS nach **Energy Appliance Scheduler** suchen.
9. **Herunterladen** auswählen.
10. Home Assistant vollständig neu starten.

Danach kann die Integration unter **Einstellungen → Geräte & Dienste → Integration hinzufügen** eingerichtet werden.

## Aktualisierung über HACS

Sobald im GitHub-Repository eine neuere Version veröffentlicht wurde, zeigt HACS das verfügbare Update an.

1. HACS öffnen.
2. **Integrationen** auswählen.
3. **Energy Appliance Scheduler** öffnen.
4. **Aktualisieren** beziehungsweise **Herunterladen** auswählen.
5. Home Assistant nach der Aktualisierung vollständig neu starten.

Bereits angelegte Integrationseinträge, Geräte und Einstellungen bleiben erhalten. Erforderliche Konfigurationsmigrationen führt die Integration automatisch aus.

## Manuelle Installation

Alternativ kann die Integration manuell installiert werden.

Den Ordner

```text
custom_components/energy_appliance_scheduler
```

nach

```text
/config/custom_components/
```

kopieren und Home Assistant vollständig neu starten.

Bei einer manuellen Aktualisierung wird der vorhandene Ordner vollständig durch den Ordner aus dem neuen Paket ersetzt.

## Einmalige Grundeinrichtung

Unter **Einstellungen → Geräte & Dienste → Integration hinzufügen** nach **Energy Appliance Scheduler** suchen.

Die Integration kann nur einmal eingerichtet werden. Innerhalb dieses einen Integrationseintrags können anschließend beliebig viele Geräte hinzugefügt, bearbeitet und gelöscht werden.

Bei der Grundeinrichtung werden ausgewählt:

- Günstigphasensensor aus `energy_storage_control`
- Binärsensor **Aktuell günstig**
- Sensor **Aktueller Strompreis**
- optional ein oder mehrere Alexa-Geräte
- Alexa-Ausgabeart
- Alexa-Ruhezeit mit Beginn und Ende
- Lautstärke der Alexa-Meldungen
- bearbeitbare Alexa-Texte

Nach Abschluss der Grundeinrichtung wird das erste zu steuernde Gerät angelegt.

## Alexa-Ruhezeit und Ansagelautstärke

Bei der Ersteinrichtung und bei jeder späteren globalen Neukonfiguration werden folgende Alexa-Einstellungen abgefragt:

- **Alexa-Ruhezeit aktivieren**
- **Beginn der Alexa-Ruhezeit**
- **Ende der Alexa-Ruhezeit**
- **Lautstärke der Alexa-Meldungen** in Prozent

Standardmäßig ist die Ruhezeit von **22:00 Uhr bis 06:00 Uhr** aktiviert und die Ansagelautstärke auf **40 %** eingestellt. Der Ruhezeitraum darf über Mitternacht hinausgehen. Ein Zeitraum von 22:00 bis 06:00 Uhr unterdrückt daher alle Alexa-Ausgaben ab 22:00 Uhr bis unmittelbar vor 06:00 Uhr.

Während der Ruhezeit:

- wird keine Meldung über Alexa ausgegeben,
- wird die Lautstärke der Alexa-Geräte nicht verändert,
- bleiben alle Meldungen vollständig im Home-Assistant-Log erhalten.

Außerhalb der Ruhezeit setzt die Integration die ausgewählten Alexa-Geräte unmittelbar vor jeder Meldung über `media_player.volume_set` auf die konfigurierte Lautstärke. Da Alexa Media Player keinen verlässlichen separaten Lautstärkeparameter ausschließlich für eine einzelne TTS- oder Ankündigungsnachricht bereitstellt, bleibt die Gerätelautstärke anschließend auf diesem Wert.

Die Einstellungen können später unter **Einstellungen → Geräte & Dienste → Energy Appliance Scheduler → Konfigurieren** geändert werden.

## Alexa-Texte

Für Alexa-Ansagen sind Standardtexte hinterlegt. Diese können bei der Einrichtung und später über den Konfigurieren-Dialog bearbeitet werden.

Unterstützte Platzhalter:

- `{device}` – Gerätename
- `{program}` – ausgewähltes Programm
- `{program_phrase}` – vollständig formulierter Programmzusatz
- `{start_date}` – Startdatum
- `{start_time}` – Startzeit
- `{price}` – Preis in Cent/kWh
- `{schedule}` – vollständig formulierter Startplan
- `{error}` – Fehlertext

## Geräte hinzufügen und bearbeiten

Weitere Geräte werden im vorhandenen Integrationseintrag als native Config-Subentries angelegt. Jedes konfigurierte Haushaltsgerät erscheint als eigenständiges Home-Assistant-Gerät.

Je Gerät werden konfiguriert:

1. Gerätename und optionales Symbol
2. optionale Programmentität
3. Verhalten der Programmauswahl
4. optionale Vorbereitungsaktionen
5. Startaktionen
6. optionale Entität für den Betriebszustand
7. Zustände, die einen laufenden Betrieb kennzeichnen
8. Zeitlimit für die Startbestätigung

## Optionale Programmauswahl

Als Programmquelle kann eine vorhandene `select`- oder `input_select`-Entität ausgewählt werden. Daraus erstellt die Integration eine eigene native Programmauswahl am verwalteten Gerät.

Unterstützte Betriebsarten:

- **Programm auswählen und anschließend Startaktionen ausführen**
- **Programmauswahl startet das Gerät unmittelbar**

Damit werden unter anderem folgende Gerätekonzepte unterstützt:

- Programmvorwahl mit separater Starttaste
- Start durch Auswahl eines aktuellen Programms
- Geräte ohne Programmauswahl, die ausschließlich über Taste, Schalter oder Skript gestartet werden

## Startaktionen

Die Startlogik wird mit dem nativen Home-Assistant-Aktionseditor konfiguriert. Dadurch sind unter anderem möglich:

- `button.press`
- `switch.turn_on`
- `select.select_option`
- vorhandene Home-Assistant-Skripte
- mehrstufige Aktionsfolgen
- Programmwahl mit anschließendem Startbefehl

Startaktionen sind nur dann optional, wenn bereits die Programmauswahl selbst den Gerätestart auslöst.

## Hinweise für Home Connect

Dieser Abschnitt gilt nur, wenn Geräte über die in Home Assistant enthaltene [Home-Connect-Integration](https://www.home-assistant.io/integrations/home_connect/) gesteuert werden.

Bei Home-Connect-Geräten kann die Auswahl eines Programms zugleich den Programmstart auslösen. Für diesen Fall sollte die entsprechende Home-Connect-`select`-Entität als optionale Programmentität hinterlegt und das Verhalten **Programmauswahl startet das Gerät unmittelbar** gewählt werden. Dieselbe `select.select_option`-Aktion sollte dann nicht nochmals zusätzlich als Startaktion hinterlegt werden.

Home Connect akzeptiert einen Fernstart nur, wenn der aktuelle Gerätezustand dies erlaubt. Bei `SDK.Error.ProgramNotWritable` sind insbesondere folgende Punkte zu prüfen:

- Gerät ist eingeschaltet und in Home Connect online
- Gerätetür ist vollständig geschlossen
- Fernstart beziehungsweise Fernbedienung ist direkt am Gerät aktiviert
- es läuft kein anderes Programm
- das gewählte Programm ist im aktuellen Gerätezustand verfügbar

Die Integration kann diese gerätespezifische Freigabe nicht erzwingen. Sie protokolliert weiterhin den vollständigen technischen Fehler mit Traceback, zeigt im Status und in Alexa-Meldungen für bekannte Home-Connect-Fehler jedoch eine verständliche deutsche Erklärung an. Nach einem fehlgeschlagenen Start bleibt die Startfreigabe aus, damit kein unbeabsichtigter Wiederholungsstart erfolgt.

## Optionaler Betriebszustand

Optional kann eine vorhandene Entität ausgewählt werden, die den Betriebszustand des Geräts meldet. Die Zustände, die als laufender Betrieb gelten, werden kommagetrennt angegeben, beispielsweise:

```text
on,running,active
```

Nach dem Startbefehl wartet die Integration innerhalb des konfigurierten Zeitlimits auf einen dieser Zustände. Ist ein Betriebszustand konfiguriert, erzeugt die Integration zusätzlich die native Binärsensor-Entität **In Betrieb**.

## Native Entitäten je Gerät

Immer vorhanden:

- **Startfreigabe**
- **Startmodus**
- **Fester Startzeitpunkt**
- **Geplanter Start**
- **Geplanter Strompreis**
- **Status**

Optional:

- **Programm** – bei konfigurierter Programmentität
- **In Betrieb** – bei konfigurierter Betriebszustandsentität

## Startmodi

### Aktuelle oder nächste Günstigphase

Wird die Startfreigabe während einer bereits aktiven Günstigphase eingeschaltet, startet das Gerät unmittelbar nach der Aktivierungsansage.

Ist noch keine Günstigphase aktiv, plant die Integration den Start für die nächste von `energy_storage_control` gemeldete Günstigphase. Sobald `binary_sensor.esc_…_favorable_now` aktiv wird, werden die konfigurierten Aktionen ausgeführt.

### Fester Zeitpunkt

Der Nutzer legt einen festen Startzeitpunkt fest. Dieser Startmodus ist **nicht vom Strompreis abhängig**. Die Startfreigabe wird auch dann angenommen und das Gerät zum gewählten Zeitpunkt gestartet, wenn für diesen Zeitpunkt kein Preis im ESC-Sensor vorhanden ist.

Liegt ein passender 15-Minuten-Preis vor, wird er ausschließlich informativ im Sensor **Geplanter Strompreis**, im Log und gegebenenfalls in der Alexa-Meldung verwendet. Er ist keine Startbedingung und verändert den festgelegten Startzeitpunkt nicht.

## Einmalige Startfreigabe

Ein automatischer Start erfolgt ausschließlich, wenn der Nutzer die native Entität **Startfreigabe** zuvor eingeschaltet hat.

Nach Ausgabe des Startbefehls wird die Startfreigabe zwingend wieder ausgeschaltet. Dadurch kann ein Gerätebefehl weder durch ein späteres Sensorupdate noch durch einen Neustart ungewollt ein zweites Mal ausgelöst werden.

Ist ein Betriebszustandssensor konfiguriert, wartet die Integration anschließend auf die Startbestätigung. Bei einem Timeout bleibt die Startfreigabe ausgeschaltet und der Status wechselt auf **Start nicht bestätigt**.

## Strompreisermittlung

Bei einem Start zur **aktuellen oder nächsten Günstigphase** ist ein gültiger Preis erforderlich, weil die Planung ausdrücklich auf den von `energy_storage_control` bereitgestellten Günstigphasen und Preisdaten beruht.

Bei einem **festen Zeitpunkt** wird der Strompreis dagegen nicht kontrolliert und ist keine Voraussetzung für den Start. Ein vorhandener Preis wird nur informativ aus dem passenden 15-Minuten-Eintrag des Attributs `data` gelesen. Fehlt dieser Eintrag, bleibt der feste Start trotzdem aktiv und wird zum vorgegebenen Zeitpunkt ausgeführt.

Beim tatsächlichen Start wird – sofern verfügbar – zusätzlich der aktuelle numerische Zustand von `sensor.esc_…_current_price` ausgewertet, damit Log, Sensor und Alexa-Meldung den zu diesem Zeitpunkt gültigen Preis nennen können. Ein fehlender Preis darf einen festen Zeitstart jedoch niemals verhindern.

## Protokollierung im Home-Assistant-Log

Alle von der Integration erzeugten Benutzer- und Statusmeldungen werden zusätzlich in das Home-Assistant-Log geschrieben. Das gilt unabhängig davon, ob Alexa-Geräte konfiguriert oder erreichbar sind.

Protokolliert werden unter anderem:

- Aktivierung und Deaktivierung der Startfreigabe
- berechneter Startzeitpunkt und zugehöriger Strompreis
- Änderungen von Startmodus, Startzeit und Programm
- Start und Abschluss der konfigurierten Aktionsfolge
- automatisches Zurücksetzen der Startfreigabe
- Warten auf den optionalen Betriebszustand
- erfolgreiche oder ausgebliebene Startbestätigung
- Alexa-Texte im vollständigen Wortlaut
- Unterdrückung einer Alexa-Ausgabe während der konfigurierten Ruhezeit
- eingestellte Ansagelautstärke und Fehler beim Setzen der Alexa-Lautstärke
- Planungs-, Preis-, Alexa- und Gerätefehler
- Laden und Entladen der Integration sowie Wiederherstellung gespeicherter Startpläne

Routine- und Planungsmeldungen werden mit der Protokollstufe `INFO` ausgegeben. Nicht bestätigte Starts und fehlende Preisdaten bei einem Günstigphasenstart erscheinen als `WARNING`; bei einem festen Zeitstart sind fehlende Preisdaten kein Fehler. Startfehler und nicht ausführbare Aktionen erscheinen als `ERROR`. Bei technischen Ausnahmen wird zusätzlich der vollständige Traceback protokolliert.

Der Logger der Integration lautet:

```text
custom_components.energy_appliance_scheduler
```

Damit auch sämtliche `INFO`-Meldungen sicher im Home-Assistant-Log erscheinen, kann in der `configuration.yaml` folgende Logger-Konfiguration ergänzt werden:

```yaml
logger:
  default: warning
  logs:
    custom_components.energy_appliance_scheduler: info
```

Nach einer Änderung der Logger-Konfiguration muss Home Assistant vollständig neu gestartet werden.

## Nachträgliche Konfiguration

### Globale Einstellungen

**Einstellungen → Geräte & Dienste → Energy Appliance Scheduler → Konfigurieren**

Dort können geändert werden:

- ESC-Günstigphasensensor
- ESC-Binärsensor **Aktuell günstig**
- ESC-Strompreissensor
- Alexa-Geräte
- Alexa-Ausgabeart
- sämtliche Alexa-Texte

### Einzelne Geräte

Im Integrationseintrag kann jeder Geräte-Untereintrag separat bearbeitet oder gelöscht werden. Änderbar sind unter anderem:

- Gerätename
- Programmquelle
- Programmverhalten
- Vorbereitungsaktionen
- Startaktionen
- Betriebszustandsentität
- bestätigende Betriebszustände
- Timeout

## Weiterführende Links

- [Energy Appliance Scheduler auf GitHub](https://github.com/Q14siX/energy_appliance_scheduler)
- [Energy Storage Control auf GitHub](https://github.com/Q14siX/energy_storage_control)
- [HACS auf GitHub](https://github.com/hacs/integration)
- [Alexa Media Player auf GitHub](https://github.com/alandtse/alexa_media_player)
- [Home Assistant](https://www.home-assistant.io/)
- [Home Connect in Home Assistant](https://www.home-assistant.io/integrations/home_connect/)

## Branding

<p align="center">
  <img src="https://raw.githubusercontent.com/Q14siX/energy_appliance_scheduler/main/custom_components/energy_appliance_scheduler/brand/icon.png" alt="Energy Appliance Scheduler Icon" width="260">
</p>

Die transparenten Brand-Dateien befinden sich im Repository unter:

```text
custom_components/energy_appliance_scheduler/brand/icon.png
custom_components/energy_appliance_scheduler/brand/logo.png
```

In der README werden Logo und Icon bewusst über `raw.githubusercontent.com` eingebunden. Dadurch werden sie nicht nur auf GitHub selbst, sondern auch in der von HACS gerenderten README angezeigt.

## Lizenz

Dieses Projekt wird unter der **MIT License** veröffentlicht.

```text
Copyright (c) 2026 Q14siX
```

Die MIT-Lizenz erlaubt insbesondere die private und kommerzielle Nutzung, Veränderung, Weitergabe und Veröffentlichung des Codes, sofern der Copyright- und Lizenzhinweis erhalten bleibt. Die Software wird ohne Gewährleistung oder Haftungszusage bereitgestellt. Der vollständige Lizenztext befindet sich in der Datei [`LICENSE`](LICENSE).

## Sicherheitshinweis

Nur Geräte automatisiert starten, die für einen unbeaufsichtigten Start geeignet, korrekt vorbereitet und vom Hersteller dafür freigegeben sind. Türen, Wasseranschlüsse, Abluftwege und Programme müssen vor dem Einschalten der Startfreigabe geprüft sein.
