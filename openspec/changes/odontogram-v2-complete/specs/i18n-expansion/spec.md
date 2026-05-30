# Spec: i18n-expansion

**Change:** odontogram-v2-complete
**Spec ID:** I18N
**Tipo:** Frontend
**Prioridad:** P2
**Estado:** Borrador
**Fecha:** 2026-04-02
**Dependencia:** `state-catalog`, `surface-selection`

---

## 1. Resumen

El odontograma v1 contribuye ~21 claves al sistema de i18n de ClinicForge (distribuidas entre el nodo raíz y el nodo `odontogram`). La v2 introduce aproximadamente 110 claves nuevas por idioma, cubriendo: los 42 estados del catálogo expandido, las 2 categorías, las 3 condiciones, las 5 superficies, los labels de tabs, los textos de los nuevos modales (`SymbolSelectorModal` y `StateConditionModal`), y mensajes de estado general de la UI.

Todas las claves nuevas se ubican dentro del nodo `odontogram` en los archivos `es.json`, `en.json` y `fr.json`, siguiendo la estructura de sub-nodos ya existente. Las traducciones deben ser precisas y usar terminología odontológica correcta, no traducciones literales.

---

## 2. Requisitos Funcionales

### REQ-I18N-001 — Claves para los 42 estados del catálogo

Cada uno de los 42 estados definidos en `state-catalog` DEBE tener su clave de traducción bajo `odontogram.states.{id}` en los tres archivos de idioma. El label debe corresponder al `labelKey` del catálogo: `"odontogram.states.{id}"`.

### REQ-I18N-002 — Claves para las 2 categorías

Se DEBEN agregar 2 claves bajo `odontogram.categories`:
- `odontogram.categories.preexistente`
- `odontogram.categories.lesion`

### REQ-I18N-003 — Claves para las 3 condiciones

Se DEBEN agregar 3 claves bajo `odontogram.conditions`:
- `odontogram.conditions.bueno`
- `odontogram.conditions.malo`
- `odontogram.conditions.indefinido`

### REQ-I18N-004 — Claves para las 5 superficies

Se DEBEN agregar 5 claves bajo `odontogram.surfaces`:
- `odontogram.surfaces.occlusal`
- `odontogram.surfaces.mesial`
- `odontogram.surfaces.distal`
- `odontogram.surfaces.buccal`
- `odontogram.surfaces.lingual`

### REQ-I18N-005 — Claves para los tabs de dentición

Se DEBEN agregar 2 claves bajo `odontogram.tabs`:
- `odontogram.tabs.permanent`
- `odontogram.tabs.deciduous`

### REQ-I18N-006 — Claves para el SymbolSelectorModal

Se DEBEN agregar claves bajo `odontogram.modal`:
- `odontogram.modal.title`
- `odontogram.modal.search_placeholder`
- `odontogram.modal.apply`
- `odontogram.modal.back`
- `odontogram.modal.select_state`
- `odontogram.modal.no_results`
- `odontogram.modal.all_categories`

### REQ-I18N-007 — Claves para el StateConditionModal

Se DEBEN agregar claves bajo `odontogram.condition_modal`:
- `odontogram.condition_modal.title`
- `odontogram.condition_modal.select_condition`
- `odontogram.condition_modal.select_color`
- `odontogram.condition_modal.apply`
- `odontogram.condition_modal.back`
- `odontogram.condition_modal.custom_color`
- `odontogram.condition_modal.reset_color`

### REQ-I18N-008 — Claves de UI general del odontograma

Se DEBEN agregar claves bajo `odontogram`:
- `odontogram.no_selection` — texto cuando ninguna superficie está seleccionada
- `odontogram.surface_selected` — texto indicando qué superficie está activa (ej: "Superficie: Oclusal")
- `odontogram.tooth_selected` — texto indicando qué pieza está activa (ej: "Pieza 16")
- `odontogram.clear_surface` — botón para limpiar el estado de una superficie
- `odontogram.clear_tooth` — botón para limpiar todos los estados de una pieza
- `odontogram.legend_title` — título de la leyenda
- `odontogram.legend_empty` — texto cuando no hay estados en uso

### REQ-I18N-009 — Terminología clínica correcta

Las traducciones deben usar terminología odontológica profesional en cada idioma. En particular:
- Español: términos del sistema FDI y nomenclatura utilizada en Argentina/Latinoamérica.
- Inglés: terminología estándar en odontología anglosajona (no traducciones literales del español).
- Francés: terminología dental estándar francesa.

### REQ-I18N-010 — Estructura JSON sin romper el archivo existente

Las nuevas claves DEBEN agregarse dentro del nodo `"odontogram"` existente en cada archivo. No deben reemplazar las 21 claves ya existentes. El JSON resultante DEBE ser válido (sin trailing commas, sin duplicados).

---

## 3. Detalle Técnico

### 3.1. Estructura del nodo `odontogram` después de la expansión

```json
{
  "odontogram": {
    // ── Claves existentes (no tocar) ──────────────────────────────────
    "save": "...",
    "save_error": "...",
    // ... resto de las 21 claves actuales ...

    // ── Nuevas claves ─────────────────────────────────────────────────
    "no_selection":   "...",
    "surface_selected": "...",
    "tooth_selected": "...",
    "clear_surface":  "...",
    "clear_tooth":    "...",
    "legend_title":   "...",
    "legend_empty":   "...",

    "tabs": {
      "permanent":  "...",
      "deciduous":  "..."
    },

    "categories": {
      "preexistente": "...",
      "lesion":       "..."
    },

    "conditions": {
      "bueno":     "...",
      "malo":      "...",
      "indefinido": "..."
    },

    "surfaces": {
      "occlusal": "...",
      "mesial":   "...",
      "distal":   "...",
      "buccal":   "...",
      "lingual":  "..."
    },

    "modal": {
      "title":             "...",
      "search_placeholder": "...",
      "apply":             "...",
      "back":              "...",
      "select_state":      "...",
      "no_results":        "...",
      "all_categories":    "..."
    },

    "condition_modal": {
      "title":            "...",
      "select_condition": "...",
      "select_color":     "...",
      "apply":            "...",
      "back":             "...",
      "custom_color":     "...",
      "reset_color":      "..."
    },

    "states": {
      // ── PREEXISTENTE ────────────────────────────────────────────────
      "healthy":               "...",
      "implante":              "...",
      "radiografia":           "...",
      "restauracion_resina":   "...",
      "restauracion_amalgama": "...",
      "restauracion_temporal": "...",
      "sellador_fisuras":      "...",
      "carilla":               "...",
      "puente":                "...",
      "corona_porcelana":      "...",
      "corona_resina":         "...",
      "corona_metalceramica":  "...",
      "corona_temporal":       "...",
      "incrustacion":          "...",
      "onlay":                 "...",
      "poste":                 "...",
      "perno":                 "...",
      "fibras_ribbond":        "...",
      "tratamiento_conducto":  "...",
      "protesis_removible":    "...",
      "diente_erupcion":       "...",
      "diente_no_erupcionado": "...",
      "ausente":               "...",
      "treatment_planned":     "...",
      "otra_preexistencia":    "...",
      // ── LESIÓN ──────────────────────────────────────────────────────
      "mancha_blanca":          "...",
      "surco_profundo":         "...",
      "caries":                 "...",
      "caries_penetrante":      "...",
      "necrosis_pulpar":        "...",
      "proceso_apical":         "...",
      "fistula":                "...",
      "indicacion_extraccion":  "...",
      "abrasion":               "...",
      "abfraccion":             "...",
      "atricion":               "...",
      "erosion":                "...",
      "fractura_horizontal":    "...",
      "fractura_vertical":      "...",
      "movilidad":              "...",
      "hipomineralizacion_mih": "...",
      "otra_lesion":            "..."
    }
  }
}
```

### 3.2. Tabla de traducciones completa — `odontogram.states`

#### Estados — Categoría PREEXISTENTE

| ID | Español (es) | Inglés (en) | Francés (fr) |
|----|-------------|------------|-------------|
| `healthy` | Sano | Healthy | Sain |
| `implante` | Implante | Implant | Implant |
| `radiografia` | Radiografía | X-Ray | Radiographie |
| `restauracion_resina` | Restauración de resina | Composite restoration | Restauration en résine composite |
| `restauracion_amalgama` | Restauración de amalgama | Amalgam restoration | Restauration en amalgame |
| `restauracion_temporal` | Restauración temporal | Temporary restoration | Restauration temporaire |
| `sellador_fisuras` | Sellador de fosas y fisuras | Pit and fissure sealant | Scellement de fissures |
| `carilla` | Carilla | Veneer | Facette |
| `puente` | Puente | Bridge | Bridge |
| `corona_porcelana` | Corona de porcelana/zirconio | Porcelain/zirconia crown | Couronne en porcelaine/zircone |
| `corona_resina` | Corona de resina | Composite crown | Couronne en composite |
| `corona_metalceramica` | Corona metal-cerámica | Metal-ceramic crown | Couronne métal-céramique |
| `corona_temporal` | Corona temporal | Temporary crown | Couronne temporaire |
| `incrustacion` | Incrustación | Inlay | Inlay |
| `onlay` | Onlay | Onlay | Onlay |
| `poste` | Poste | Post | Tenon radiculaire |
| `perno` | Perno | Screw post | Pivot |
| `fibras_ribbond` | Fibras Ribbond | Ribbond fiber | Fibre Ribbond |
| `tratamiento_conducto` | Tratamiento de conducto | Root canal treatment | Traitement endodontique |
| `protesis_removible` | Prótesis removible | Removable denture | Prothèse amovible |
| `diente_erupcion` | Diente en erupción | Erupting tooth | Dent en éruption |
| `diente_no_erupcionado` | Diente no erupcionado | Unerupted tooth | Dent incluse |
| `ausente` | Ausente | Absent | Absent |
| `treatment_planned` | Tratamiento planificado | Treatment planned | Traitement planifié |
| `otra_preexistencia` | Otra preexistencia | Other pre-existing | Autre préexistant |

#### Estados — Categoría LESIÓN

| ID | Español (es) | Inglés (en) | Francés (fr) |
|----|-------------|------------|-------------|
| `mancha_blanca` | Mancha blanca | White spot lesion | Tache blanche |
| `surco_profundo` | Surco profundo | Deep groove | Sillon profond |
| `caries` | Caries | Caries | Carie |
| `caries_penetrante` | Caries penetrante | Penetrating caries | Carie pénétrante |
| `necrosis_pulpar` | Necrosis pulpar | Pulp necrosis | Nécrose pulpaire |
| `proceso_apical` | Proceso apical | Periapical lesion | Lésion périapicale |
| `fistula` | Fístula | Fistula | Fistule |
| `indicacion_extraccion` | Indicación de extracción | Extraction indicated | Extraction indiquée |
| `abrasion` | Abrasión | Abrasion | Abrasion |
| `abfraccion` | Abfracción | Abfraction | Abfraction |
| `atricion` | Atrición | Attrition | Attrition |
| `erosion` | Erosión | Erosion | Érosion |
| `fractura_horizontal` | Fractura horizontal | Horizontal fracture | Fracture horizontale |
| `fractura_vertical` | Fractura vertical | Vertical fracture | Fracture verticale |
| `movilidad` | Movilidad | Mobility | Mobilité |
| `hipomineralizacion_mih` | Hipomineralización molar-incisivo | Molar-incisor hypomineralization | Hypominéralisation molaire-incisive |
| `otra_lesion` | Otra lesión | Other lesion | Autre lésion |

### 3.3. Tabla de traducciones completa — Claves de UI

#### `odontogram.categories`

| Clave | Español (es) | Inglés (en) | Francés (fr) |
|-------|-------------|------------|-------------|
| `preexistente` | Preexistente | Pre-existing | Préexistant |
| `lesion` | Lesión | Lesion | Lésion |

#### `odontogram.conditions`

| Clave | Español (es) | Inglés (en) | Francés (fr) |
|-------|-------------|------------|-------------|
| `bueno` | Bueno | Good | Bon |
| `malo` | Malo | Poor | Mauvais |
| `indefinido` | Indefinido | Unspecified | Indéfini |

#### `odontogram.surfaces`

| Clave | Español (es) | Inglés (en) | Francés (fr) |
|-------|-------------|------------|-------------|
| `occlusal` | Oclusal | Occlusal | Occlusale |
| `mesial` | Mesial | Mesial | Mésiale |
| `distal` | Distal | Distal | Distale |
| `buccal` | Vestibular | Buccal / Labial | Vestibulaire |
| `lingual` | Lingual / Palatino | Lingual / Palatal | Linguale / Palatale |

> Nota para `buccal`: en español dental la cara externa del diente se llama "Vestibular" (no "Bucal"). Se usa "Vestibular" en es.json. En francés se usa "Vestibulaire". Para lingual/palatino, depende de si es diente anterior (palatino) o posterior (lingual); se usa el término más genérico `Lingual / Palatino` para evitar ambigüedad.

#### `odontogram.tabs`

| Clave | Español (es) | Inglés (en) | Francés (fr) |
|-------|-------------|------------|-------------|
| `permanent` | Permanente | Permanent | Permanent |
| `deciduous` | Temporal / Decidua | Deciduous / Primary | Temporaire / Déciduale |

#### `odontogram.modal` (SymbolSelectorModal)

| Clave | Español (es) | Inglés (en) | Francés (fr) |
|-------|-------------|------------|-------------|
| `title` | Seleccionar estado | Select state | Sélectionner un état |
| `search_placeholder` | Buscar estado... | Search state... | Rechercher un état... |
| `apply` | Aplicar | Apply | Appliquer |
| `back` | Volver | Back | Retour |
| `select_state` | Elegí un estado para esta superficie | Choose a state for this surface | Choisissez un état pour cette surface |
| `no_results` | No se encontraron estados | No states found | Aucun état trouvé |
| `all_categories` | Todas las categorías | All categories | Toutes les catégories |

#### `odontogram.condition_modal` (StateConditionModal)

| Clave | Español (es) | Inglés (en) | Francés (fr) |
|-------|-------------|------------|-------------|
| `title` | Condición y color | Condition & color | Condition et couleur |
| `select_condition` | Seleccionar condición | Select condition | Sélectionner la condition |
| `select_color` | Color del estado | State color | Couleur de l'état |
| `apply` | Aplicar | Apply | Appliquer |
| `back` | Volver | Back | Retour |
| `custom_color` | Color personalizado | Custom color | Couleur personnalisée |
| `reset_color` | Restablecer color por defecto | Reset to default color | Réinitialiser la couleur |

#### `odontogram` — Claves de UI general

| Clave | Español (es) | Inglés (en) | Francés (fr) |
|-------|-------------|------------|-------------|
| `no_selection` | Seleccioná una pieza para comenzar | Select a tooth to get started | Sélectionnez une dent pour commencer |
| `surface_selected` | Superficie: {{surface}} | Surface: {{surface}} | Surface : {{surface}} |
| `tooth_selected` | Pieza {{tooth}} | Tooth {{tooth}} | Dent {{tooth}} |
| `clear_surface` | Limpiar superficie | Clear surface | Effacer la surface |
| `clear_tooth` | Limpiar pieza | Clear tooth | Effacer la dent |
| `legend_title` | Estados en uso | States in use | États utilisés |
| `legend_empty` | Sin estados registrados | No states recorded | Aucun état enregistré |

### 3.4. JSON completo para `es.json` (nodo expandido)

Las siguientes claves se AGREGAN dentro del nodo `"odontogram"` existente:

```json
"no_selection": "Seleccioná una pieza para comenzar",
"surface_selected": "Superficie: {{surface}}",
"tooth_selected": "Pieza {{tooth}}",
"clear_surface": "Limpiar superficie",
"clear_tooth": "Limpiar pieza",
"legend_title": "Estados en uso",
"legend_empty": "Sin estados registrados",

"tabs": {
  "permanent": "Permanente",
  "deciduous": "Temporal / Decidua"
},

"categories": {
  "preexistente": "Preexistente",
  "lesion": "Lesión"
},

"conditions": {
  "bueno": "Bueno",
  "malo": "Malo",
  "indefinido": "Indefinido"
},

"surfaces": {
  "occlusal": "Oclusal",
  "mesial": "Mesial",
  "distal": "Distal",
  "buccal": "Vestibular",
  "lingual": "Lingual / Palatino"
},

"modal": {
  "title": "Seleccionar estado",
  "search_placeholder": "Buscar estado...",
  "apply": "Aplicar",
  "back": "Volver",
  "select_state": "Elegí un estado para esta superficie",
  "no_results": "No se encontraron estados",
  "all_categories": "Todas las categorías"
},

"condition_modal": {
  "title": "Condición y color",
  "select_condition": "Seleccionar condición",
  "select_color": "Color del estado",
  "apply": "Aplicar",
  "back": "Volver",
  "custom_color": "Color personalizado",
  "reset_color": "Restablecer color por defecto"
},

"states": {
  "healthy": "Sano",
  "implante": "Implante",
  "radiografia": "Radiografía",
  "restauracion_resina": "Restauración de resina",
  "restauracion_amalgama": "Restauración de amalgama",
  "restauracion_temporal": "Restauración temporal",
  "sellador_fisuras": "Sellador de fosas y fisuras",
  "carilla": "Carilla",
  "puente": "Puente",
  "corona_porcelana": "Corona de porcelana/zirconio",
  "corona_resina": "Corona de resina",
  "corona_metalceramica": "Corona metal-cerámica",
  "corona_temporal": "Corona temporal",
  "incrustacion": "Incrustación",
  "onlay": "Onlay",
  "poste": "Poste",
  "perno": "Perno",
  "fibras_ribbond": "Fibras Ribbond",
  "tratamiento_conducto": "Tratamiento de conducto",
  "protesis_removible": "Prótesis removible",
  "diente_erupcion": "Diente en erupción",
  "diente_no_erupcionado": "Diente no erupcionado",
  "ausente": "Ausente",
  "treatment_planned": "Tratamiento planificado",
  "otra_preexistencia": "Otra preexistencia",
  "mancha_blanca": "Mancha blanca",
  "surco_profundo": "Surco profundo",
  "caries": "Caries",
  "caries_penetrante": "Caries penetrante",
  "necrosis_pulpar": "Necrosis pulpar",
  "proceso_apical": "Proceso apical",
  "fistula": "Fístula",
  "indicacion_extraccion": "Indicación de extracción",
  "abrasion": "Abrasión",
  "abfraccion": "Abfracción",
  "atricion": "Atrición",
  "erosion": "Erosión",
  "fractura_horizontal": "Fractura horizontal",
  "fractura_vertical": "Fractura vertical",
  "movilidad": "Movilidad",
  "hipomineralizacion_mih": "Hipomineralización molar-incisivo",
  "otra_lesion": "Otra lesión"
}
```

### 3.5. JSON completo para `en.json` (nodo expandido)

```json
"no_selection": "Select a tooth to get started",
"surface_selected": "Surface: {{surface}}",
"tooth_selected": "Tooth {{tooth}}",
"clear_surface": "Clear surface",
"clear_tooth": "Clear tooth",
"legend_title": "States in use",
"legend_empty": "No states recorded",

"tabs": {
  "permanent": "Permanent",
  "deciduous": "Deciduous / Primary"
},

"categories": {
  "preexistente": "Pre-existing",
  "lesion": "Lesion"
},

"conditions": {
  "bueno": "Good",
  "malo": "Poor",
  "indefinido": "Unspecified"
},

"surfaces": {
  "occlusal": "Occlusal",
  "mesial": "Mesial",
  "distal": "Distal",
  "buccal": "Buccal / Labial",
  "lingual": "Lingual / Palatal"
},

"modal": {
  "title": "Select state",
  "search_placeholder": "Search state...",
  "apply": "Apply",
  "back": "Back",
  "select_state": "Choose a state for this surface",
  "no_results": "No states found",
  "all_categories": "All categories"
},

"condition_modal": {
  "title": "Condition & color",
  "select_condition": "Select condition",
  "select_color": "State color",
  "apply": "Apply",
  "back": "Back",
  "custom_color": "Custom color",
  "reset_color": "Reset to default color"
},

"states": {
  "healthy": "Healthy",
  "implante": "Implant",
  "radiografia": "X-Ray",
  "restauracion_resina": "Composite restoration",
  "restauracion_amalgama": "Amalgam restoration",
  "restauracion_temporal": "Temporary restoration",
  "sellador_fisuras": "Pit and fissure sealant",
  "carilla": "Veneer",
  "puente": "Bridge",
  "corona_porcelana": "Porcelain/zirconia crown",
  "corona_resina": "Composite crown",
  "corona_metalceramica": "Metal-ceramic crown",
  "corona_temporal": "Temporary crown",
  "incrustacion": "Inlay",
  "onlay": "Onlay",
  "poste": "Post",
  "perno": "Screw post",
  "fibras_ribbond": "Ribbond fiber",
  "tratamiento_conducto": "Root canal treatment",
  "protesis_removible": "Removable denture",
  "diente_erupcion": "Erupting tooth",
  "diente_no_erupcionado": "Unerupted tooth",
  "ausente": "Absent",
  "treatment_planned": "Treatment planned",
  "otra_preexistencia": "Other pre-existing",
  "mancha_blanca": "White spot lesion",
  "surco_profundo": "Deep groove",
  "caries": "Caries",
  "caries_penetrante": "Penetrating caries",
  "necrosis_pulpar": "Pulp necrosis",
  "proceso_apical": "Periapical lesion",
  "fistula": "Fistula",
  "indicacion_extraccion": "Extraction indicated",
  "abrasion": "Abrasion",
  "abfraccion": "Abfraction",
  "atricion": "Attrition",
  "erosion": "Erosion",
  "fractura_horizontal": "Horizontal fracture",
  "fractura_vertical": "Vertical fracture",
  "movilidad": "Mobility",
  "hipomineralizacion_mih": "Molar-incisor hypomineralization",
  "otra_lesion": "Other lesion"
}
```

### 3.6. JSON completo para `fr.json` (nodo expandido)

```json
"no_selection": "Sélectionnez une dent pour commencer",
"surface_selected": "Surface : {{surface}}",
"tooth_selected": "Dent {{tooth}}",
"clear_surface": "Effacer la surface",
"clear_tooth": "Effacer la dent",
"legend_title": "États utilisés",
"legend_empty": "Aucun état enregistré",

"tabs": {
  "permanent": "Permanent",
  "deciduous": "Temporaire / Déciduale"
},

"categories": {
  "preexistente": "Préexistant",
  "lesion": "Lésion"
},

"conditions": {
  "bueno": "Bon",
  "malo": "Mauvais",
  "indefinido": "Indéfini"
},

"surfaces": {
  "occlusal": "Occlusale",
  "mesial": "Mésiale",
  "distal": "Distale",
  "buccal": "Vestibulaire",
  "lingual": "Linguale / Palatale"
},

"modal": {
  "title": "Sélectionner un état",
  "search_placeholder": "Rechercher un état...",
  "apply": "Appliquer",
  "back": "Retour",
  "select_state": "Choisissez un état pour cette surface",
  "no_results": "Aucun état trouvé",
  "all_categories": "Toutes les catégories"
},

"condition_modal": {
  "title": "Condition et couleur",
  "select_condition": "Sélectionner la condition",
  "select_color": "Couleur de l'état",
  "apply": "Appliquer",
  "back": "Retour",
  "custom_color": "Couleur personnalisée",
  "reset_color": "Réinitialiser la couleur"
},

"states": {
  "healthy": "Sain",
  "implante": "Implant",
  "radiografia": "Radiographie",
  "restauracion_resina": "Restauration en résine composite",
  "restauracion_amalgama": "Restauration en amalgame",
  "restauracion_temporal": "Restauration temporaire",
  "sellador_fisuras": "Scellement de fissures",
  "carilla": "Facette",
  "puente": "Bridge",
  "corona_porcelana": "Couronne en porcelaine/zircone",
  "corona_resina": "Couronne en composite",
  "corona_metalceramica": "Couronne métal-céramique",
  "corona_temporal": "Couronne temporaire",
  "incrustacion": "Inlay",
  "onlay": "Onlay",
  "poste": "Tenon radiculaire",
  "perno": "Pivot",
  "fibras_ribbond": "Fibre Ribbond",
  "tratamiento_conducto": "Traitement endodontique",
  "protesis_removible": "Prothèse amovible",
  "diente_erupcion": "Dent en éruption",
  "diente_no_erupcionado": "Dent incluse",
  "ausente": "Absent",
  "treatment_planned": "Traitement planifié",
  "otra_preexistencia": "Autre préexistant",
  "mancha_blanca": "Tache blanche",
  "surco_profundo": "Sillon profond",
  "caries": "Carie",
  "caries_penetrante": "Carie pénétrante",
  "necrosis_pulpar": "Nécrose pulpaire",
  "proceso_apical": "Lésion périapicale",
  "fistula": "Fistule",
  "indicacion_extraccion": "Extraction indiquée",
  "abrasion": "Abrasion",
  "abfraccion": "Abfraction",
  "atricion": "Attrition",
  "erosion": "Érosion",
  "fractura_horizontal": "Fracture horizontale",
  "fractura_vertical": "Fracture verticale",
  "movilidad": "Mobilité",
  "hipomineralizacion_mih": "Hypominéralisation molaire-incisive",
  "otra_lesion": "Autre lésion"
}
```

### 3.7. Uso en componentes React

```tsx
// SymbolSelectorModal.tsx
const { t } = useTranslation();

// Label de un estado del catálogo
const stateLabel = t(state.labelKey);
// Equivale a: t('odontogram.states.implante') → "Implante"

// Label de categoría
const categoryLabel = t(`odontogram.categories.${state.category}`);
// → "Preexistente" o "Lesión"

// Surface selected message (con interpolación)
const msg = t('odontogram.surface_selected', { surface: t(`odontogram.surfaces.${activeSurface}`) });
// → "Superficie: Oclusal"
```

### 3.8. Conteo de claves nuevas

| Grupo | Claves por idioma |
|-------|-------------------|
| `odontogram.states.*` | 42 |
| `odontogram.categories.*` | 2 |
| `odontogram.conditions.*` | 3 |
| `odontogram.surfaces.*` | 5 |
| `odontogram.tabs.*` | 2 |
| `odontogram.modal.*` | 7 |
| `odontogram.condition_modal.*` | 7 |
| `odontogram.*` (raíz, no anidadas) | 7 |
| **Total** | **75 claves × 3 idiomas = 225 traducciones** |

---

## 4. Escenarios

### Escenario I18N-01 — Traducción de un estado en español

```gherkin
Given el idioma activo es 'es'
When el SymbolSelectorModal renderiza el estado con id='tratamiento_conducto'
Then muestra el texto "Tratamiento de conducto"
And NOT "tratamiento_conducto" (sin claves sin traducir)
```

### Escenario I18N-02 — Traducción de un estado en inglés

```gherkin
Given el idioma activo es 'en'
When el SymbolSelectorModal renderiza el estado con id='tratamiento_conducto'
Then muestra el texto "Root canal treatment"
And NOT "Tratamiento de conducto" (sin fallback al español)
```

### Escenario I18N-03 — Traducción de un estado en francés

```gherkin
Given el idioma activo es 'fr'
When el SymbolSelectorModal renderiza el estado con id='tratamiento_conducto'
Then muestra el texto "Traitement endodontique"
```

### Escenario I18N-04 — Label de categoría

```gherkin
Given el idioma activo es 'es'
When el SymbolSelectorModal muestra el badge de categoría del estado 'caries'
Then muestra el texto "Lesión" (no "lesion" crudo)
```

### Escenario I18N-05 — Label de superficie con interpolación

```gherkin
Given el idioma activo es 'es'
And la superficie activa es 'occlusal'
When el componente Odontogram renderiza el indicador de superficie
Then muestra "Superficie: Oclusal"
```

```gherkin
Given el idioma activo es 'en'
When el componente Odontogram renderiza el indicador de superficie
Then muestra "Surface: Occlusal"
```

### Escenario I18N-06 — Buscador en SymbolSelectorModal

```gherkin
Given el idioma activo es 'es'
When el SymbolSelectorModal se abre
Then el placeholder del buscador es "Buscar estado..."
When el usuario escribe "caries"
Then aparecen estados cuyo label contiene "caries" (insensible a mayúsculas)
```

### Escenario I18N-07 — Sin resultados de búsqueda

```gherkin
Given el idioma activo es 'fr'
When el usuario busca "zzzzz" (sin resultados)
Then el modal muestra "Aucun état trouvé"
```

### Escenario I18N-08 — Condición en StateConditionModal

```gherkin
Given el idioma activo es 'es'
When el StateConditionModal muestra las 3 opciones de condición
Then muestra los botones "Bueno", "Malo", "Indefinido"
Given el idioma activo es 'fr'
Then muestra los botones "Bon", "Mauvais", "Indéfini"
```

### Escenario I18N-09 — Tab de dentición

```gherkin
Given el idioma activo es 'es'
When el componente OdontogramTabs renderiza los 2 tabs
Then el primer tab dice "Permanente"
And el segundo tab dice "Temporal / Decidua"
Given el idioma activo es 'en'
Then el segundo tab dice "Deciduous / Primary"
```

### Escenario I18N-10 — Sin claves huérfanas

```gherkin
Given el catálogo ODONTOGRAM_STATES (42 estados)
When verifico que cada estado tiene su clave en es.json, en.json y fr.json
Then todos los 42 estados × 3 idiomas = 126 combinaciones existen
And NINGUNA retorna el fallback de i18n (la clave misma como string)
```

### Escenario I18N-11 — No romper claves existentes

```gherkin
Given el odontograma v1 usaba t('odontogram.save') en español
When agrego las claves nuevas a es.json
Then t('odontogram.save') sigue retornando el valor original
And ninguna clave existente queda modificada o eliminada
```

---

## 5. Criterios de Aceptación

| ID | Criterio | Verificación |
|----|----------|-------------|
| CA-I18N-01 | `es.json` contiene exactamente 42 claves bajo `odontogram.states` | `Object.keys(translations.odontogram.states).length === 42` |
| CA-I18N-02 | `en.json` contiene exactamente 42 claves bajo `odontogram.states` | Ídem para en |
| CA-I18N-03 | `fr.json` contiene exactamente 42 claves bajo `odontogram.states` | Ídem para fr |
| CA-I18N-04 | Los IDs de `odontogram.states` en los 3 archivos son idénticos al catálogo | Test de sincronía vs `ODONTOGRAM_STATES` |
| CA-I18N-05 | Ningún valor de traducción contiene la clave misma como texto (sin traducir) | Regex check: ningún valor === su clave |
| CA-I18N-06 | Los 3 archivos son JSON válido después de la modificación | `JSON.parse()` sin excepción |
| CA-I18N-07 | Las claves existentes del odontograma v1 no fueron modificadas | Diff muestra solo adiciones |
| CA-I18N-08 | La interpolación `{{surface}}` y `{{tooth}}` funciona correctamente | Test de render con `t('odontogram.surface_selected', { surface: 'Oclusal' })` |
| CA-I18N-09 | El término `buccal` se traduce como "Vestibular" en es.json (no "Bucal") | Verificación directa del JSON |
| CA-I18N-10 | El término `lingual` incluye la alternativa palatino en es.json y fr.json | Verificación directa del JSON |
| CA-I18N-11 | `hipomineralizacion_mih` se traduce correctamente en los 3 idiomas | No queda como clave cruda en ningún idioma |
| CA-I18N-12 | Los 3 archivos tienen exactamente las mismas claves bajo `odontogram` (estructura simétrica) | Test de igualdad de key sets entre los 3 archivos |

---

## 6. Archivos Afectados

| Archivo | Acción | Descripción |
|---------|--------|-------------|
| `frontend_react/src/locales/es.json` | **MODIFICAR** | Agregar 75 claves nuevas dentro del nodo `odontogram` |
| `frontend_react/src/locales/en.json` | **MODIFICAR** | Agregar 75 claves nuevas dentro del nodo `odontogram` |
| `frontend_react/src/locales/fr.json` | **MODIFICAR** | Agregar 75 claves nuevas dentro del nodo `odontogram` |
| `frontend_react/src/components/odontogram/SymbolSelectorModal.tsx` | **CREAR** | Consume `odontogram.modal.*`, `odontogram.states.*`, `odontogram.categories.*` |
| `frontend_react/src/components/odontogram/StateConditionModal.tsx` | **CREAR** | Consume `odontogram.condition_modal.*`, `odontogram.conditions.*`, `odontogram.surfaces.*` |
| `frontend_react/src/components/Odontogram.tsx` | **MODIFICAR** | Consume `odontogram.tabs.*`, `odontogram.no_selection`, `odontogram.tooth_selected`, etc. |
| `tests/test_i18n_odontogram.ts` | **CREAR** | Verifica sincronía de claves entre los 3 archivos y el catálogo de estados |

---

## 7. Dependencias

| Tipo | Dependencia | Detalle |
|------|-------------|---------|
| **Bloqueante** | `state-catalog` | Las 42 claves `odontogram.states.*` deben corresponder exactamente a los `id` del catálogo. Sin el catálogo definido, los IDs no están fijos. |
| **Bloqueante** | `surface-selection` | Los nombres de las 5 superficies (`occlusal`, `mesial`, `distal`, `buccal`, `lingual`) deben estar acordados antes de crear las claves. |
| **Bloqueante inversa** | `symbol-selector-modal` | El `SymbolSelectorModal` usa `t(state.labelKey)` y `t('odontogram.modal.*')`. Sin estas claves, los labels son strings crudos. |
| **Bloqueante inversa** | `state-condition-color` | El `StateConditionModal` usa `t('odontogram.condition_modal.*')` y `t('odontogram.conditions.*')`. |
| **Bloqueante inversa** | `dentition-tabs` | Los tabs usan `t('odontogram.tabs.permanent')` y `t('odontogram.tabs.deciduous')`. |
| **Sin dependencia** | `data-model-evolution` | Los cambios de modelo de datos son independientes de las traducciones. |
| **Sin dependencia** | `svg-pdf-renderer` | El renderer Python no usa el sistema i18n; los labels en PDF son hardcodeados en español. |
| **Sin dependencia** | `nova-tools-update` | Nova retorna texto en español directamente; no usa el sistema i18n de React. |
