# dump_folder Electron GUI

Seconda GUI desktop basata su Electron, separata dalla versione Tkinter.

## Avvio

Da [desktop/electron](/C:/Users/andre/odoo-17/cyberfolk/tools/dump_folder/desktop/electron):

```powershell
npm.cmd install
npm.cmd start
```

## Funzioni incluse

- scelta di una root locale
- navigazione tree con lazy loading
- selezione tri-state include/exclude
- riepilogo dinamico della selezione
- scelta output e formato `txt`, `md`, `html`
- generazione dump locale

## Note

- la GUI Electron non sostituisce quella Tkinter: vive in parallelo
- usa il filesystem locale tramite processi Electron
- salva preferenze in `app.getPath("userData")`
