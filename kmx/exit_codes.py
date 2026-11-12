"""Exit-Codes der Kommandozeile."""

CLI_EXIT_OK = 0
# Datei fehlt, Formatfehler oder Selbsttest fehlgeschlagen
CLI_EXIT_ERROR = 1
# Prüfung fehlgeschlagen oder Kosten gestiegen
CLI_EXIT_REJECTED = 2
# offizieller Verifier fehlt oder lehnt ab
CLI_EXIT_OFFICIAL_GATE = 3
