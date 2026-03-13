import React, { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import api from '../api/axios';

import es from '../locales/es.json';
import en from '../locales/en.json';
import fr from '../locales/fr.json';

export type UiLanguage = 'es' | 'en' | 'fr';

const translations: Record<UiLanguage, Record<string, unknown>> = {
  es: es as Record<string, unknown>,
  en: en as Record<string, unknown>,
  fr: fr as Record<string, unknown>,
};

function getNested(obj: Record<string, unknown>, path: string): string | undefined {
  const keys = path.split('.');
  let current: unknown = obj;
  for (const key of keys) {
    if (current == null || typeof current !== 'object') return undefined;
    current = (current as Record<string, unknown>)[key];
  }
  return typeof current === 'string' ? current : undefined;
}

interface LanguageContextType {
  language: UiLanguage;
  setLanguage: (lang: UiLanguage) => void;
  t: (key: string, data?: Record<string, any>) => string;
  isLoading: boolean;
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

const STORAGE_KEY = 'ui_language';

export const LanguageProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [language, setLanguageState] = useState<UiLanguage>(() => {
    const stored = localStorage.getItem(STORAGE_KEY) as UiLanguage | null;
    return stored === 'es' || stored === 'fr' ? stored : 'en';
  });
  const [isLoading, setIsLoading] = useState(true);

  const setLanguage = useCallback((lang: UiLanguage) => {
    setLanguageState(lang);
    localStorage.setItem(STORAGE_KEY, lang);
  }, []);

  useEffect(() => {
    const userProfile = localStorage.getItem('USER_PROFILE');
    if (!userProfile) {
      setIsLoading(false);
      return;
    }
    api
      .get<{ ui_language?: string }>('/admin/settings/clinic')
      .then((res) => {
        const lang = res.data?.ui_language;
        if (lang === 'es' || lang === 'fr' || lang === 'en') {
          // If we have a stored language that is different from server, 
          // we might want to keep it if it was just changed, but server should be source of truth.
          // For now, let's sync server -> state/localStorage
          setLanguageState(lang);
          localStorage.setItem(STORAGE_KEY, lang);
        }
      })
      .catch((err) => {
        console.error("Error loading language settings:", err);
      })
      .finally(() => setIsLoading(false));
  }, []);

  const t = useCallback(
    (key: string, data?: Record<string, any>): string => {
      let value = getNested(translations[language], key);
      if (!value) return key;

      if (data) {
        Object.entries(data).forEach(([k, v]) => {
          value = (value as string).replace(new RegExp(`{{${k}}}`, 'g'), String(v));
        });
      }
      return value as string;
    },
    [language]
  );

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t, isLoading }}>
      {children}
    </LanguageContext.Provider>
  );
};

export function useTranslation() {
  const ctx = useContext(LanguageContext);
  if (ctx === undefined) throw new Error('useTranslation must be used within LanguageProvider');
  return ctx;
}
