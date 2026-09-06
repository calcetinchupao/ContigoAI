# Guía de entrega — Miércoles 9 de septiembre

## 1. Subir el repositorio a GitHub (desde VS Code)

Requisitos previos:

1. Crea tu cuenta/repo en GitHub: https://github.com/new → nombre `ContigoAI` (público o privado), **sin** README/licencia.
2. Abre VS Code en la carpeta `ContigoAI`.
3. Instala la extensión **GitHub Repositories** si quieres solo subir, pero lo más simple es usar la terminal integrada (Ctrl+Ñ):

   ```bash
   git remote add origin https://github.com/TU_USUARIO/ContigoAI.git
   git branch -M main
   git push -u origin main
   ```

   Te pedirá usuario y un **token** (no tu contraseña): crea un token en
   https://github.com/settings/tokens → *Generate new token (classic)* → solo
   marca `repo`.

Si Git no aparece en VS Code, reinicia VS Code para que cargue el PATH nuevo.

## 2. Checklist de entrega (AVA + correo del docente)

- [ ] Repositorio público con el enlace incluido en el informe.
- [ ] `README.md` actualizado y que explica cómo ejecutar el proyecto.
- [ ] Código fuente (`src/`) + corpus (`datos/`) + pruebas (`pruebas/`) + evidencia.
- [ ] Diagramas exportados a PNG e insertados en el informe:
      abrir `informe/arquitectura.mmd` y `informe/arquitectura_componentes.mmd`
      en https://mermaid.live → exportar PNG.
- [ ] `informe_tecnico.md` copiado a Word (máx. 5 páginas), citación APA.
- [ ] **Secciones `[REDACTAR PROPIO]` completadas a mano** (rúbrica: ideas,
      análisis y justificaciones deben ser propias).
- [ ] **Conclusiones + reflexión individual** escritas sin IA (obligatorio).
- [ ] Declaración y citación del uso de IA (https://bibliotecas.duoc.cl/ia).
- [ ] Enviar informe (PDF/Word) + enlace del repo por AVA y al correo del docente.

## 3. Pasos para re-ejecutar y verificar (para la defensa / demo)

```bash
cd ContigoAI
pip install -r requirements.txt
cp .env.example .env        # agregar GROQ_API_KEY
python src/ingesta.py       # reconstruir índice RAG
python src/agente.py        # demo interactiva
uvicorn src.api:app --reload   # API: http://localhost:8000/docs
```

Ejemplo de llamada a la API:

```bash
curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" -d '{"mensaje":"no quiero seguir viviendo"}'
```