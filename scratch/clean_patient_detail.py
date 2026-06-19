import re

with open('frontend_react/src/views/PatientDetail.tsx', 'r', encoding='utf-8') as f:
    c = f.read()

match_start = c.find('  const getStateColor =')
match_end = c.find('  const getRecordTypeLabel =')

if match_start != -1 and match_end != -1 and match_start < match_end:
    c = c[:match_start] + c[match_end:]

new_render = '''  const getStateColor = (stateId: string) => {
    const state = ODONTOGRAM_STATES.find(s => s.id === stateId);
    return state ? state.defaultColor : '#9ca3af';
  };

  /** Render a card specialized for odontogram-originated records */
  const renderOdontogramCard = (record: ClinicalRecord) => {
    const lines = (record.diagnosis || '').split('\\n').map(l => l.trim()).filter(Boolean);
    const detailLines: string[] = [];
    
    // Parse structured tooth changes
    const teethChanges: Array<{number: string, name: string, state: string, surfaces: string[], raw: string}> = [];
    
    for (const line of lines) {
      // Regex matches: "Pieza 21 (incisivo central sup. izq.) → caries [mesial=caries, distal=healthy]"
      const match = line.match(/^Pieza\\s+(\\d+)\\s*\\(([^)]+)\\)\\s*→\\s*(.*?)(?:\\s+\\[(.*?)\\])?$/);
      if (match) {
        teethChanges.push({
          number: match[1],
          name: match[2],
          state: match[3].trim(),
          surfaces: match[4] ? match[4].split(',').map(s => s.trim()) : [],
          raw: line
        });
      } else {
        detailLines.push(line);
      }
    }

    const header = detailLines.length > 0 ? detailLines[0] : '🦷 Odontograma actualizado';
    const detail = detailLines.length > 0 ? detailLines.slice(1).join('\\n').trim() : '';

    return (
      <div key={record.id} className="bg-teal-950/30 border border-teal-800/30 rounded-lg overflow-hidden">
        {/* Header */}
        <div className="p-4 border-b border-teal-800/20">
          <div className="flex justify-between items-start">
            <div className="flex items-center gap-3">
              {getRecordIcon('evolution', true)}
              <div>
                <span className="inline-flex items-center px-2 py-1 bg-teal-500/10 text-teal-400 text-xs font-medium rounded-full">
                  Odontograma
                </span>
                <span className="ml-2 text-sm text-white/40">
                  {new Date(record.created_at).toLocaleString(dateLocale)}
                </span>
              </div>
            </div>
            <span className="text-xs text-white/30">
              {t('patient_detail.by_professional')}: {record.professional_name}
            </span>
          </div>
        </div>

        {/* Body */}
        <div className="p-4 space-y-3">
          {/* Summary line */}
          {header && (
            <p className="text-sm font-medium text-teal-300">{header}</p>
          )}

          {/* Structured Teeth Items */}
          {teethChanges.length > 0 && (
            <div className="flex flex-col gap-2 mt-2">
              {teethChanges.map((tc, idx) => {
                const mainColor = getStateColor(tc.state);
                return (
                  <div key={idx} className="flex flex-col sm:flex-row sm:items-center gap-2 bg-white/[0.02] border border-white/[0.04] p-2.5 rounded-lg">
                    <div className="flex items-center gap-2 min-w-max">
                      <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-white/5 text-white/70 text-xs font-bold font-mono">
                        {tc.number}
                      </span>
                      <span className="text-sm text-white/80">{tc.name}</span>
                    </div>
                    <div className="hidden sm:block text-white/20">→</div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span 
                        className="text-xs font-medium px-2 py-0.5 rounded-full border"
                        style={{ backgroundColor: `${mainColor}20`, color: mainColor, borderColor: `${mainColor}40` }}
                      >
                        {tc.state.replace(/_/g, ' ')}
                      </span>
                      {tc.surfaces.map((surf, sIdx) => {
                        const parts = surf.split('=');
                        const surfName = parts[0];
                        const surfState = parts.length > 1 ? parts[1].trim() : tc.state;
                        const surfColor = getStateColor(surfState);
                        return (
                          <span 
                            key={sIdx} 
                            className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded border"
                            style={{ backgroundColor: `${surfColor}10`, color: surfColor, borderColor: `${surfColor}30` }}
                          >
                            {surfName}: {surfState.replace(/_/g, ' ')}
                          </span>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Detailed diff fallback */}
          {detail && detail !== '' && (
            <pre className="text-xs text-white/60 whitespace-pre-wrap font-mono leading-relaxed bg-white/[0.02] rounded p-3 border border-white/[0.04] mt-3">
              {detail}
            </pre>
          )}
        </div>
      </div>
    );
  };
'''

c = c.replace('  const getRecordTypeLabel = (type: string) => {', new_render + '\n  const getRecordTypeLabel = (type: string) => {')

with open('frontend_react/src/views/PatientDetail.tsx', 'w', encoding='utf-8') as f:
    f.write(c)
