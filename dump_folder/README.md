# dump_folder

> Dump ricorsivo del contenuto di una directory in un singolo file testuale.

---

## Scopo:

- Avere una rappresentazione piatta e completa di una cartella
- Includere il contenuto dei file testuali inline
- Mantenere un ordine stabile e riproducibile
- evitare archivi binari (zip, tar) e compressioni

---

## Usi da terminale:

```bash
dump_folder 
dump_folder .
dump_folder /percorso/cartella
```

---

## Per farlo partire:

Col terminale vai nella radice della repo e fai:

```bash
chmod +x dump_folder/dump_folder.py
mkdir -p ~/bin
ln -s ~/path/assoluto/per/tools/dump_folder/dump_folder.py ~/bin/dump_folder
```
