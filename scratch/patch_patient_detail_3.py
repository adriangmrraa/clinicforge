import re

with open("c:/Users/Asus/Documents/estabilizacion/Laura Delgado/clinicforge/frontend_react/src/views/PatientDetail.tsx", "r", encoding="utf-8") as f:
    content = f.read()

# We want to replace renderOdontogramCard body

NEW_CODE = """
  /** Render a card specialized for odontogram-originated records */
  const renderOdontogramCard = (record: ClinicalRecord) => {
    const lines = (record.diagnosis || '').split('\\n').map(l => l.trim()).filter(Boolean);
    const detailLines: string[] = [];
    
    // Parse structured tooth changes
    const teethChanges: Array<{number: string, name: string, state: string, surfaces: string[], raw: string}> = [];
    let currentTooth: { number: string, name: string, state: string, surfaces: string[], raw: string } | null = null;
    
    for (const line of lines) {
      // 1. Check for AI format: "Pieza 21 (incisivo central sup. izq.) → caries [mesial=caries]"
      const matchAI = line.match(/^Pieza\\s+(\\d+)\\s*\\(([^)]+)\\)\\s*→\\s*(.*?)(?:\\s+\\[(.*?)\\])?$/);
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

      // 2. Check for UI format Header: "Diente 14 — 1er premolar sup. der."
      const matchUIHeader = line.match(/^Diente\\s+(\\d+)\\s*—\\s*(.*)$/);
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

      // 3. Check for UI format Surface: "Oclusal: sano → Implante"
      if (currentTooth) {
        const matchUISurface = line.match(/^([^:]+):\\s*([^→]+)→\\s*(.*)$/);
        if (matchUISurface) {
          const surfName = matchUISurface[1].trim();
          const newState = matchUISurface[3].trim();
          
          if (surfName.toLowerCase() === 'todas las superficies') {
             currentTooth.state = newState;
             currentTooth.surfaces = ['todas=' + newState];
          } else {
             currentTooth.surfaces.push(`${surfName}=${newState}`);
             currentTooth.state = newState; // Keep the last seen state as the main fallback state
          }
          continue;
        } else {
           // Not a surface line, tooth block ended
           teethChanges.push(currentTooth);
           currentTooth = null;
        }
      }

      detailLines.push(line);
    }
    
    if (currentTooth) {
      teethChanges.push(currentTooth);
    }

    const header = detailLines.length > 0 ? detailLines[0] : '🦷 Odontograma actualizado';
    const detail = detailLines.length > 0 ? detailLines.slice(1).join('\\n').trim() : '';

    return (
"""

pattern = re.compile(
    r"  /\*\* Render a card specialized for odontogram-originated records \*/\n  const renderOdontogramCard = \(record: ClinicalRecord\) => \{\n.*?    return \(\n",
    re.DOTALL
)

if not pattern.search(content):
    print("Could not find renderOdontogramCard!")
else:
    new_content = pattern.sub(NEW_CODE, content)
    with open("c:/Users/Asus/Documents/estabilizacion/Laura Delgado/clinicforge/frontend_react/src/views/PatientDetail.tsx", "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Patched successfully!")

