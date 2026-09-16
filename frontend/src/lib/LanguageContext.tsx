import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { translations, type Locale } from './translations';
import { setApiLocale } from './api';

interface I18nContextValue {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (key: string) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

const STORAGE_KEY = 'bpmn.locale';

function readStoredLocale(): Locale {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw === 'en' || raw === 'de') return raw;
  } catch {

  }
  return 'en';
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(readStoredLocale);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, locale);
    } catch {

    }
    document.documentElement.lang = locale;
    setApiLocale(locale); 
  }, [locale]);

  const setLocale = (l: Locale) => setLocaleState(l);

  const t = (key: string): string => {
    const dict = translations[locale] ?? translations.en;
    if (key in dict) return dict[key];
    if (key in translations.en) return translations.en[key];
    return key;
  };

  return <I18nContext.Provider value={{ locale, setLocale, t }}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    throw new Error('useI18n() must be used within a <LanguageProvider>');
  }
  return ctx;
}
