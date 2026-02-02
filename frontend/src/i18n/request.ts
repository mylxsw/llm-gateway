import { cookies, headers } from "next/headers";
import { getRequestConfig } from "next-intl/server";

import {
  defaultLocale,
  localeCookieName,
  locales,
  type Locale,
} from "./config";

const isLocale = (value?: string): value is Locale =>
  !!value && locales.includes(value as Locale);

export default getRequestConfig(async () => {
  let locale: Locale = defaultLocale;

  // In static export mode, cookies() throws during build.
  // We catch and fall back to default locale.
  try {
    const store = await cookies();
    const cookieLocale = store.get(localeCookieName)?.value;
    if (isLocale(cookieLocale)) {
      locale = cookieLocale;
    }
  } catch {
    // Static export build - use default locale
  }

  return {
    locale,
    messages: (await import(`../../messages/${locale}.json`)).default,
  };
});
