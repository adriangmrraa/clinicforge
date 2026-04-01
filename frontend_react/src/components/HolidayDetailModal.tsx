import { useState, useEffect } from 'react';
import { PartyPopper, X } from 'lucide-react';
import { format, parseISO } from 'date-fns';
import { es } from 'date-fns/locale';
import { useTranslation } from '../context/LanguageContext';
import api from '../api/axios';
import type { Holiday } from '../views/AgendaView';

interface HolidayDetailModalProps {
  holiday: Holiday | null;
  isOpen: boolean;
  onClose: () => void;
  onSaved: () => void;
}

export default function HolidayDetailModal({ holiday, isOpen, onClose, onSaved }: HolidayDetailModalProps) {
  const { t } = useTranslation();

  const isWorkingDay = holiday?.holiday_type === 'override_open';

  const [workingToggle, setWorkingToggle] = useState(false);
  const [startTime, setStartTime] = useState('09:00');
  const [endTime, setEndTime] = useState('13:00');
  const [saving, setSaving] = useState(false);
  const [timeError, setTimeError] = useState(false);

  useEffect(() => {
    if (holiday) {
      setWorkingToggle(holiday.holiday_type === 'override_open');
      setStartTime(holiday.custom_hours_start || holiday.custom_hours?.start || '09:00');
      setEndTime(holiday.custom_hours_end || holiday.custom_hours?.end || '13:00');
      setTimeError(false);
    }
  }, [holiday]);

  useEffect(() => {
    if (workingToggle && startTime && endTime) {
      setTimeError(startTime >= endTime);
    } else {
      setTimeError(false);
    }
  }, [startTime, endTime, workingToggle]);

  if (!isOpen || !holiday) return null;

  const formattedDate = (() => {
    try {
      return format(parseISO(holiday.date), "EEEE d 'de' MMMM 'de' yyyy", { locale: es });
    } catch {
      return holiday.date;
    }
  })();

  const handleSave = async () => {
    if (workingToggle && timeError) return;

    setSaving(true);
    try {
      const currentlyWorking = isWorkingDay;

      if (workingToggle !== currentlyWorking) {
        // Toggle changed — call toggle endpoint
        await api.post('/admin/holidays/toggle', {
          date: holiday.date,
          name: holiday.name,
        });
      }

      if (workingToggle && holiday.id) {
        // Save custom hours
        await api.put(`/admin/holidays/${holiday.id}`, {
          holiday_type: 'override_open',
          custom_hours_start: startTime,
          custom_hours_end: endTime,
        });
      }

      onSaved();
    } catch (err) {
      console.error('Error saving holiday config:', err);
    } finally {
      setSaving(false);
    }
  };

  const badgeTypeLabel = (() => {
    if (holiday.holiday_type === 'closure') return t('holidays.closure');
    if (holiday.holiday_type === 'override_open') return t('holidays.specialHours');
    return t('holidays.nationalHoliday');
  })();

  const badgeTypeColor = (() => {
    if (holiday.holiday_type === 'closure') return 'bg-red-500/10 text-red-400';
    if (holiday.holiday_type === 'override_open') return 'bg-amber-500/10 text-amber-400';
    return 'bg-red-500/10 text-red-400';
  })();

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[60] flex items-center justify-center p-4">
      <div className="bg-[#0d1117] border border-white/[0.08] rounded-2xl shadow-2xl max-w-md w-full mx-4 overflow-hidden">
        {/* Header */}
        <div className="flex items-start justify-between p-6 pb-4">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-full bg-red-500/15 flex items-center justify-center shrink-0">
              <PartyPopper size={22} className="text-red-400" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white leading-tight">{holiday.name}</h2>
              <p className="text-sm text-white/40 mt-0.5 capitalize">{formattedDate}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-xl hover:bg-white/[0.06] text-white/40 hover:text-white transition-colors shrink-0"
          >
            <X size={18} />
          </button>
        </div>

        {/* Badges */}
        <div className="flex items-center gap-2 px-6 pb-5">
          <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${badgeTypeColor}`}>
            {badgeTypeLabel}
          </span>
          {holiday.is_recurring && (
            <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-blue-500/10 text-blue-400">
              {t('holidays.recurring')}
            </span>
          )}
        </div>

        {/* Divider */}
        <div className="h-px bg-white/[0.06] mx-6" />

        {/* Body */}
        <div className="p-6 space-y-5">
          {/* Working day toggle */}
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold text-white">{t('holidays.workingDay')}</p>
              <p className="text-xs text-white/40 mt-0.5">{t('holidays.workingDayDescription')}</p>
            </div>
            {/* Custom toggle */}
            <button
              onClick={() => setWorkingToggle(prev => !prev)}
              className={`relative w-12 h-6 rounded-full transition-colors duration-200 focus:outline-none shrink-0 ${
                workingToggle ? 'bg-blue-600' : 'bg-white/[0.12]'
              }`}
              role="switch"
              aria-checked={workingToggle}
            >
              <span
                className={`absolute top-1 left-1 w-4 h-4 rounded-full bg-white shadow-md transition-transform duration-200 ${
                  workingToggle ? 'translate-x-6' : 'translate-x-0'
                }`}
              />
            </button>
          </div>

          {/* Time pickers */}
          {workingToggle && (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-white/50 uppercase tracking-wider">
                    {t('holidays.startTime')}
                  </label>
                  <input
                    type="time"
                    value={startTime}
                    onChange={e => setStartTime(e.target.value)}
                    className="w-full bg-white/[0.04] border border-white/[0.08] text-white rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/30 transition-colors"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-white/50 uppercase tracking-wider">
                    {t('holidays.endTime')}
                  </label>
                  <input
                    type="time"
                    value={endTime}
                    onChange={e => setEndTime(e.target.value)}
                    className="w-full bg-white/[0.04] border border-white/[0.08] text-white rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/30 transition-colors"
                  />
                </div>
              </div>
              {timeError && (
                <p className="text-xs text-red-400 font-medium">
                  {t('holidays.invalidTimeRange')}
                </p>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center gap-3 px-6 pb-6">
          <button
            onClick={onClose}
            className="flex-1 py-2.5 px-4 rounded-xl bg-white/[0.06] hover:bg-white/[0.10] text-white/70 hover:text-white text-sm font-semibold transition-colors"
          >
            {t('holidays.cancel')}
          </button>
          <button
            onClick={handleSave}
            disabled={saving || (workingToggle && timeError)}
            className="flex-1 py-2.5 px-4 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-semibold transition-colors"
          >
            {saving ? '...' : t('holidays.save')}
          </button>
        </div>
      </div>
    </div>
  );
}
