import { getRequestConfig } from "next-intl/server";

import { defaultLocale } from "./config";

// For static export mode, we use client-side IntlProvider
// This config is only used during build time for prerendering
export default getRequestConfig(async () => {
  return {
    locale: defaultLocale,
    timeZone: "UTC",
    messages: (await import(`../../messages/${defaultLocale}.json`)).default,
  };
});
