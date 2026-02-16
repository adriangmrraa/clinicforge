import React, { useRef, useEffect } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

interface DateStripProps {
    selectedDate: Date;
    onDateSelect: (date: Date) => void;
}

export default function DateStrip({ selectedDate, onDateSelect }: DateStripProps) {
    const scrollRef = useRef<HTMLDivElement>(null);

    // Generate array of dates (e.g., +/- 15 days from selected date, or a fixed range)
    // For simplicity, let's show a rolling window centered on today/selected date
    // But to be "infinite" we'd need more logic. Let's do fixed range +/- 30 days for now.
    const dates: Date[] = [];
    const start = new Date(selectedDate);
    start.setDate(start.getDate() - 15); // Start 15 days ago

    for (let i = 0; i < 30; i++) {
        const d = new Date(start);
        d.setDate(start.getDate() + i);
        dates.push(d);
    }

    // Scroll to selected date on mount/change
    useEffect(() => {
        if (scrollRef.current) {
            // Find the selected date element index
            const index = dates.findIndex(d => d.toDateString() === selectedDate.toDateString());
            if (index >= 0) {
                // Calculate position: (Item Width + Gap) * Index
                // Approximate item width 60px
                const scrollPos = index * 68 - (scrollRef.current.clientWidth / 2) + 34;
                scrollRef.current.scrollTo({ left: scrollPos, behavior: 'smooth' });
            }
        }
    }, [selectedDate, dates.length]);

    const formatDate = (date: Date) => {
        const dayName = date.toLocaleDateString('es-ES', { weekday: 'short' });
        const dayNum = date.getDate();
        return { dayName, dayNum };
    };

    const isSelected = (date: Date) => date.toDateString() === selectedDate.toDateString();
    const isToday = (date: Date) => date.toDateString() === new Date().toDateString();

    return (
        <div className="flex flex-col bg-white border-b border-gray-100 py-2 shadow-sm shrink-0 z-10">
            <div
                ref={scrollRef}
                className="flex overflow-x-auto hide-scrollbar px-4 gap-2 pb-1"
                style={{ scrollSnapType: 'x mandatory' }}
            >
                {dates.map((date, index) => {
                    const { dayName, dayNum } = formatDate(date);
                    const selected = isSelected(date);
                    const today = isToday(date);

                    return (
                        <button
                            key={index}
                            onClick={() => onDateSelect(date)}
                            className={`flex flex-col items-center justify-center min-w-[56px] h-16 rounded-xl transition-all duration-200 snap-center
                ${selected
                                    ? 'bg-blue-600 text-white shadow-md scale-105'
                                    : today
                                        ? 'bg-blue-50 text-blue-700 border border-blue-200'
                                        : 'bg-white text-gray-500 hover:bg-gray-50 border border-transparent'
                                }
              `}
                        >
                            <span className={`text-[10px] uppercase font-semibold ${selected ? 'text-blue-100' : 'text-gray-400'}`}>
                                {dayName}
                            </span>
                            <span className={`text-xl font-bold leading-none ${selected ? 'text-white' : 'text-gray-700'}`}>
                                {dayNum}
                            </span>
                            {today && !selected && (
                                <span className="w-1 h-1 bg-blue-500 rounded-full mt-1"></span>
                            )}
                        </button>
                    );
                })}
            </div>
        </div>
    );
}
