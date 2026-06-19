const lines = [
  "Odontograma actualizado — 5 dientes modificados",
  "Diente 14 — 1er premolar sup. der.",
  "Oclusal: sano → Implante",
  "Vestibular: sano → Implante",
  "Diente 11 — Incisivo central sup. der.",
  "Oclusal: sano → Restauración de resina",
  "Vestibular: sano → Restauración de resina",
  "Diente 21 — Incisivo central sup. izq.",
  "Vestibular: sano → Caries",
  "Lingual: sano → Sellador de fosas y fisuras",
  "Mesial: sano → Caries",
  "Distal: sano → Puente",
  "Diente 46 — 1er molar inf. der.",
  "Todas las superficies: sano → Corona de porcelana/zirconia",
  "Pieza 38 (3er molar inf. izq.) → extracción [oclusal=extracción]"
];

const teethChanges = [];
const detailLines = [];
let currentTooth = null;

for (const line of lines) {
  // 1. Check for AI format
  const matchAI = line.match(/^Pieza\s+(\d+)\s*\(([^)]+)\)\s*→\s*(.*?)(?:\s+\[(.*?)\])?$/);
  if (matchAI) {
    if (currentTooth) { teethChanges.push(currentTooth); currentTooth = null; }
    teethChanges.push({
      number: matchAI[1],
      name: matchAI[2],
      state: matchAI[3].trim(),
      surfaces: matchAI[4] ? matchAI[4].split(',').map(s => s.trim()) : [],
      raw: line
    });
    continue;
  }

  // 2. Check for UI format Header
  const matchUIHeader = line.match(/^Diente\s+(\d+)\s*—\s*(.*)$/);
  if (matchUIHeader) {
    if (currentTooth) { teethChanges.push(currentTooth); }
    currentTooth = {
      number: matchUIHeader[1],
      name: matchUIHeader[2].trim(),
      state: 'modificado',
      surfaces: [],
      raw: line
    };
    continue;
  }

  // 3. Check for UI format Surface
  if (currentTooth) {
    const matchUISurface = line.match(/^([^:]+):\s*([^→]+)→\s*(.*)$/);
    if (matchUISurface) {
      const surfName = matchUISurface[1].trim();
      const newState = matchUISurface[3].trim();
      
      if (surfName.toLowerCase() === 'todas las superficies') {
         currentTooth.state = newState;
         currentTooth.surfaces = ['todas=' + newState];
      } else {
         currentTooth.surfaces.push(`${surfName}=${newState}`);
         currentTooth.state = newState;
      }
      continue;
    } else {
       teethChanges.push(currentTooth);
       currentTooth = null;
    }
  }

  detailLines.push(line);
}

if (currentTooth) {
  teethChanges.push(currentTooth);
}

console.log(JSON.stringify(teethChanges, null, 2));
console.log("Detail lines:", detailLines);
