# dump_folder

> Dump ricorsivo del contenuto di file e cartelle in un singolo file (`txt`, `md`, `html`).

## Struttura

- `engine/`: logica core del dump e modello di selezione
- `desktop/tkinter/`: GUI Tkinter
- `desktop/electron/`: GUI Electron e asset desktop
- `scripts/`: entrypoint CLI e script di supporto
- `tests/`: test automatici
- `docs/`: documentazione e specifiche

## Scopo

- Selezionare una root locale e generare un dump unico e leggibile
- Includere contenuto testuale inline
- Mantenere un ordine stabile e riproducibile
- Gestire i file binari con placeholder

## Avvio GUI Tkinter

```bash
python dump_folder/desktop/tkinter/main.py
```

La GUI attuale lavora su una singola root, permette la selezione tri-state nel tree e genera un output `txt`, `md` o `html`.

Se la GUI Tkinter incontra errori o callback che falliscono, scrive un log in:

```bash
dump_folder/logs/tkinter.log
```

## Uso da terminale

```bash
dump_folder
dump_folder .
dump_folder . txt
dump_folder . md
dump_folder . html
```

## Installazione nel terminale

```bash
chmod +x dump_folder/scripts/dump_folder.py
mkdir -p ~/bin
ln -s ~/path/assoluto/per/tools/dump_folder/scripts/dump_folder.py ~/bin/dump_folder
```

## GUI Electron

Percorso:

```bash
dump_folder/desktop/electron
```

Rebuild e riavvio rapido da Git Bash:

```bash
dump_folder/scripts/rebuild_electron_app.sh
```


---

Comando per buildare l'exe di tkinter
```bash
$ pyinstaller --onefile --windowed --icon gui/tkinter/assets/app.ico --name DumpBuilder gui/tkinter/main.py
```
