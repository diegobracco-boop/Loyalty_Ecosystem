# /publicar — Deploy manual de la landing GAS a producción

Sube `dashboard.html` / `Código.js` / `appsscript.json` al Apps Script y actualiza el
deployment estable. **Este es el flujo normal de deploy** — igual que en B2B_Ecosystem,
el deploy de la landing se hace a mano. La GitHub Action `deploy-gas.yml` quedó solo
`workflow_dispatch` (no corre en cada push) porque el secret `CLASP_CREDENTIALS` nunca
se cargó.

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
4. `clasp deployments` → confirmá que el deployment estable `AKfycbzyHV8nz_App…` muestra la versión nueva (no `@HEAD` ni una vieja). Este es el chequeo de que el deploy realmente llegó a producción.
5. Abrí la webapp (Ctrl+F5) y verificá el cambio.

## Verificar que producción está al día con `main`

El push a `main` NO deploya. Antes de asumir que algo está publicado:
```powershell
clasp deployments            # ¿qué versión está viva?
git log --oneline -5 -- dashboard.html Código.js appsscript.json   # ¿qué debería estar?
```
Si no coinciden, hacé el deploy manual (pasos de arriba) desde `main` actualizado.

## Notas

- `clasp push` solo actualiza HEAD; **la webapp no cambia hasta el `clasp deploy -i`** al deployment estable.
- Deployments: estable `AKfycbzyHV8nz_App…` · HEAD `AKfycby4_-hgcNdA…`.
- Rollback: `clasp deployments` para ver versiones, `clasp deploy -i <id> -V <version_anterior>`.
- No hay staging — el deploy es instantáneo en producción.
