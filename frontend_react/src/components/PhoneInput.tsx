import React from 'react';

interface PhoneInputProps {
  value: string;
  onChange: (value: string) => void;
  prefix?: string;
  placeholder?: string;
  disabled?: boolean;
  required?: boolean;
  className?: string;
}

/**
 * Input de teléfono con prefijo fijo.
 *
 * Muestra el prefijo (ej: "+549") como badge no editable a la izquierda.
 * El usuario escribe solo los dígitos restantes.
 * onChange devuelve la concatenación: prefix + digits.
 *
 * Ejemplo:
 *   prefix="+549" → muestra "[+549][3704868421]"
 *   onChange("+5493704868421")
 */
export default function PhoneInput({
  value,
  onChange,
  prefix = '+549',
  placeholder = 'Código de área + número',
  disabled = false,
  required = false,
  className = '',
}: PhoneInputProps) {
  // Extraer solo los dígitos después del prefijo
  const prefixDigits = prefix.replace(/\D/g, '');
  const inputDigits = value.replace(/\D/g, '');
  const displayValue = inputDigits.startsWith(prefixDigits)
    ? inputDigits.slice(prefixDigits.length)
    : inputDigits;

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    // Solo permitir dígitos
    const digits = e.target.value.replace(/\D/g, '');
    onChange(prefix + digits);
  };

  return (
    <div className={`flex items-stretch ${className}`}>
      <div className="flex items-center px-3 border border-r-0 border-white/[0.08] rounded-l-lg bg-white/[0.04] text-white/60 text-sm font-mono shrink-0">
        {prefix}
      </div>
      <input
        type="tel"
        value={displayValue}
        onChange={handleChange}
        placeholder={placeholder}
        disabled={disabled}
        required={required}
        className="w-full px-3 py-2 border border-white/[0.08] rounded-r-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-white/[0.04] text-white placeholder-white/20 disabled:opacity-50"
      />
    </div>
  );
}
