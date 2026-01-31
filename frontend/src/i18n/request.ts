import { cookies } from "next/headers";
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
  const store = await cookies();
  const cookieLocale = store.get(localeCookieName)?.value;
  const locale = isLocale(cookieLocale) ? cookieLocale : defaultLocale;

  return {
    locale,
    messages: {},
  };
});
