# Spec: i18n Cobertura Total + Whitelabel

**Versión:** 1.1  
**Fecha:** 2026-02-21  
**Estado:** En implementación  
**Autor:** Agente Antigravity  
**Origen:** Auditoría de texto hardcodeado en todas las vistas activas — ampliación del Sprint Hardening v1.0

---

## Objetivo

Completar la cobertura i18n al 100% en todas las vistas activas del frontend. Se detectaron textos hardcodeados en 6 vistas que tienen `useTranslation()` pero no lo usan en todos sus textos, más `PrivacyTermsView.tsx` que no tiene i18n en absoluto. También se elimina `"Dentalogic"` hardcodeado del código fuente para completar el modelo whitelabel. Afecta a todos los usuarios en cualquier ruta de la aplicación cuando cambian el idioma.

---

## Contexto del problema

`PrivacyTermsView.tsx` tiene:
- Todo el texto legal hardcodeado en español
- El nombre `"Dentalogic"` hardcodeado 4 veces (título, footer, y texto de políticas)
- Una fecha hardcodeada: `"19 de febrero de 2026"`
- Es pública (no requiere login), accesible desde `/privacy` y `/terms`

El resto de las 15 vistas activas ya tienen `useTranslation()`. Esta es la última que falta.

---

## Cambios en Backend

- Archivo(s) afectado(s): Ninguno
- Nuevo endpoint: No
- Cambio en lógica del agente IA: No
- Nuevo parche de BD requerido: No

---

## Cambios en Base de Datos

Ninguno.

---

## Cambios en Frontend

**Vista modificada:** `frontend_react/src/views/PrivacyTermsView.tsx`
- Agregar `useTranslation()` hook
- Reemplazar todos los textos con `t('privacy.*')` y `t('terms.*')`
- Reemplazar `"Dentalogic"` con `t('common.app_name')` (clave ya existente en los 3 locales con valor `"Dental Clinic"`)
- Reemplazar la fecha hardcodeada con la clave `t('privacy.last_updated')` para que cada idioma tenga su propio formato de fecha

**Nuevas claves i18n requeridas:** Sí — secciones `privacy` y `terms` en los 3 locales  
**Socket.IO events nuevos:** No

---

## Claves i18n a crear

### Sección `privacy` (Política de Privacidad)

```
privacy.title                    "Política de Privacidad"
privacy.last_updated             "Última actualización: 19 de febrero de 2026"
privacy.section1_title           "1. Recopilación de Información"
privacy.section1_body            "... recopila información necesaria para la gestión de clínicas dentales..."
privacy.section2_title           "2. Uso de Datos de Meta"
privacy.section2_intro           "Los datos obtenidos a través de los APIs de Meta se utilizan exclusivamente para:"
privacy.section2_item1           "Visualizar el rendimiento de tus campañas en nuestro dashboard."
privacy.section2_item2           "Atribuir mensajes entrantes de WhatsApp a anuncios específicos de Meta."
privacy.section2_item3           "Generar reportes de retorno de inversión (ROI) para el propietario de la clínica."
privacy.section3_title           "3. Protección de Datos"
privacy.section3_body            "Utilizamos cifrado AES-256 para proteger todos los tokens..."
```

### Sección `terms` (Condiciones del Servicio)

```
terms.title                      "Condiciones del Servicio"
terms.intro                      "Al utilizar [app_name], aceptas los siguientes términos:"
terms.section1_title             "1. Uso del Software"
terms.section1_body              "... es una plataforma para la gestión administrativa de clínicas..."
terms.section2_title             "2. Integraciones de Terceros"
terms.section2_body              "La integración con Meta Ads y WhatsApp depende de los términos..."
terms.section3_title             "3. Terminación"
terms.section3_body              "Puedes revocar el acceso a tus datos en cualquier momento..."
```

### Sección `legal` (header compartido)

```
legal.center_title               "Centro Legal de [app_name]"
legal.center_subtitle            "Transparencia y seguridad en el manejo de tus datos."
legal.back_button                "Volver al Inicio"
legal.footer                     "© 2026 [app_name]. Todos los derechos reservados."
```

> **Nota:** `[app_name]` usa la clave existente `common.app_name` — no crear duplicados.

---

## Criterios de Aceptación

- [ ] `PrivacyTermsView.tsx` importa y usa `useTranslation()`
- [ ] El string literal `"Dentalogic"` no existe en ningún archivo del frontend (verificable: `grep -r "Dentalogic" src/`)
- [ ] Las secciones `privacy` y `terms` existen en `es.json`, `en.json` y `fr.json`
- [ ] La vista renderiza correctamente en los 3 idiomas al cambiar el selector de idioma
- [ ] El footer usa `common.app_name` y no un nombre de marca hardcodeado
- [ ] `npm run build` completa sin errores ni warnings de claves faltantes

---

## Riesgos identificados

| Riesgo | Mitigación |
|---|---|
| El texto legal en inglés y francés sea una traducción imprecisa | Marcar las claves EN y FR con `[REVISAR CON LEGAL]` como comentario en el JSON para que el equipo las valide antes de publicar |
| `common.app_name` está en los 3 locales con valor `"Dental Clinic"` — si la clínica tiene otro nombre, se ve incorrecto | Este es el comportamiento correcto en whitelabel: el nombre real se configura por tenant en BD. La clave `common.app_name` es solo el nombre genérico de la plataforma demo |
| La fecha `"19 de febrero de 2026"` en `privacy.last_updated` queda estática | Correcto por diseño — la fecha de actualización legal debe ser explícita y controlada, no dinámica |
