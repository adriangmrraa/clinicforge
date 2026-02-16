import React from 'react';
import {
    Users, Calendar, Activity, DollarSign,
    TrendingUp, TrendingDown, Clock, Star
} from 'lucide-react';

interface KPICardProps {
    title: string;
    value: string | number;
    subtext?: string;
    trend?: 'up' | 'down' | 'neutral';
    icon: 'users' | 'calendar' | 'activity' | 'money' | 'clock' | 'star';
    color?: string;
}

const KPICard: React.FC<KPICardProps> = ({ title, value, subtext, trend, icon, color = "blue" }) => {
    const getIcon = () => {
        switch (icon) {
            case 'users': return <Users size={24} />;
            case 'calendar': return <Calendar size={24} />;
            case 'activity': return <Activity size={24} />;
            case 'money': return <DollarSign size={24} />;
            case 'clock': return <Clock size={24} />;
            case 'star': return <Star size={24} />;
            default: return <Activity size={24} />;
        }
    };

    const getColorClasses = () => {
        switch (color) {
            case 'blue': return 'bg-blue-50 text-blue-600';
            case 'green': return 'bg-green-50 text-green-600';
            case 'purple': return 'bg-purple-50 text-purple-600';
            case 'orange': return 'bg-orange-50 text-orange-600';
            default: return 'bg-gray-50 text-gray-600';
        }
    };

    return (
        <div className="card border-l-4" style={{ borderLeftColor: color === 'blue' ? 'var(--medical-500)' : color === 'green' ? 'var(--success)' : color }}>
            <div className="flex justify-between items-start">
                <div>
                    <p className="text-sm font-medium text-gray-500 mb-1">{title}</p>
                    <h3 className="text-2xl font-bold text-gray-800">{value}</h3>
                </div>
                <div className={`p-3 rounded-lg ${getColorClasses()}`}>
                    {getIcon()}
                </div>
            </div>
            {subtext && (
                <div className="mt-4 flex items-center text-sm">
                    {trend === 'up' && <TrendingUp size={16} className="text-green-500 mr-1" />}
                    {trend === 'down' && <TrendingDown size={16} className="text-red-500 mr-1" />}
                    <span className="text-gray-500">{subtext}</span>
                </div>
            )}
        </div>
    );
};

export default KPICard;
