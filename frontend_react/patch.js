const fs = require('fs');

let content = fs.readFileSync('src/views/ClinicsView.tsx', 'utf-8');

content = content.replace(
    '        coverage_by_treatment: {}, is_prepaid: false, default_copay_percent: undefined, employee_discount_percent: undefined,\n    });',
    '        coverage_by_treatment: {}, is_prepaid: false, default_copay_percent: undefined, employee_discount_percent: undefined,\n        scheduling_mode: \'immediate\', scheduling_delay_days: undefined\n    });'
);

content = content.replace(
    'setInsuranceForm({ provider_name: \'\', status: \'accepted\', requires_copay: true, sort_order: 0, is_active: true, coverage_by_treatment: {}, is_prepaid: false, default_copay_percent: undefined, employee_discount_percent: undefined });',
    'setInsuranceForm({ provider_name: \'\', status: \'accepted\', requires_copay: true, sort_order: 0, is_active: true, coverage_by_treatment: {}, is_prepaid: false, default_copay_percent: undefined, employee_discount_percent: undefined, scheduling_mode: \'immediate\', scheduling_delay_days: undefined });'
);

const uiAddition = `                            <div className="space-y-1">
                                <label className="text-sm font-semibold text-white/60">{t('settings.insurance.schedulingMode') || 'Modo de Agendamiento'}</label>
                                <select value={insuranceForm.scheduling_mode || 'immediate'} onChange={e => setInsuranceForm(p => ({ ...p, scheduling_mode: e.target.value as any }))}
                                    className="w-full px-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white outline-none">
                                    <option value="immediate" className="bg-[#0f1525]">{t('settings.insurance.modeImmediate') || 'Inmediato (Verde)'}</option>
                                    <option value="delayed" className="bg-[#0f1525]">{t('settings.insurance.modeDelayed') || 'Diferido (Amarillo)'}</option>
                                    <option value="blocked" className="bg-[#0f1525]">{t('settings.insurance.modeBlocked') || 'Bloqueado (Rojo)'}</option>
                                </select>
                            </div>
                            {insuranceForm.scheduling_mode === 'delayed' && (
                                <div className="space-y-1">
                                    <label className="text-sm font-semibold text-white/60">{t('settings.insurance.delayDays') || 'Días de diferimiento (Ej. 30)'}</label>
                                    <input type="number" min="0" value={insuranceForm.scheduling_delay_days ?? ''} onChange={e => setInsuranceForm(p => ({ ...p, scheduling_delay_days: e.target.value ? Number(e.target.value) : undefined }))}
                                        className="w-full px-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white outline-none" />
                                </div>
                            )}`;

const targetBlock = `                            <div className="space-y-1">
                                <label className="text-sm font-semibold text-white/60">{t('settings.insurance.fields.aiTemplate')}</label>
                                <textarea value={insuranceForm.ai_response_template || ''} onChange={e => setInsuranceForm(p => ({ ...p, ai_response_template: e.target.value }))} rows={3}
                                    placeholder={t('settings.insurance.fields.aiTemplatePlaceholder')}
                                    className="w-full px-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 outline-none resize-none text-sm" />
                                <p className="text-xs text-white/30">{t('settings.insurance.fields.aiTemplatePlaceholder')}</p>
                            </div>`;

content = content.replace(targetBlock, targetBlock + '\n' + uiAddition);

fs.writeFileSync('src/views/ClinicsView.tsx', content, 'utf-8');
console.log('Done!');
