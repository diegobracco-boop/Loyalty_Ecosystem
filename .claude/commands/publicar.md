# /publicar — Deploy manual de la landing GAS a producción

Sube `dashboard.html` / `Código.js` / `appsscript.json` al Apps Script y actualiza el
deployment estable. Normalmente esto lo hace **sola la GitHub Action** al mergear a
`main` — usá este comando para hotfixes, o si el secret `CLASP_CREDENTIALS` todavía
no está cargado.

**`git push` no publica la landing.** Son cosas separadas.

## Requisito

`clasp` instalado y con login:
```powershell
npm install -g @google/clasp
clasp login   # cuenta @despegar.com con acceso al proyecto 1SXEXXw…
```

## Pasos

1. Verificá que no haya cambios sin commitear (`git status`) y que estés en `main` actualizado.
2. Desde la carpeta del repo:
   ```powershell
   clasp push -f
   clasp deploy -i AKfycbzyHV8nz_AppIX81qn8QJ9dyPT77i75lBz9nerKfsjhLEk8SfSdGPXeGk52oLpXvI2Fig -d "descripción del cambio"
   ```
3. Confirmá que `clasp deploy` devolvió un nuevo `@N`.
4. Abrí la webapp (Ctrl+F5) y verificá el cambio.

## Notas

- `clasp push` solo actualiza HEAD; **la webapp no cambia hasta el `clasp deploy -i`** al deployment estable.
- Deployments: estable `AKfycbzyHV8nz_App…` · HEAD `AKfycby4_-hgcNdA…`.
- Rollback: `clasp deployments` para ver versiones, `clasp deploy -i <id> -V <version_anterior>`.
- No hay staging — el deploy es instantáneo en producción.
