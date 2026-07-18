/** SMS keretbővítés, amely a csomagok oldalról fizetési flow-val vásárolható. */
export const ADDON_CHECKOUT_CODES = ["question_pack_100"] as const;

export type AddonCheckoutCode = (typeof ADDON_CHECKOUT_CODES)[number];

export function isAddonCheckoutCode(code: string): code is AddonCheckoutCode {
  return (ADDON_CHECKOUT_CODES as readonly string[]).includes(code);
}
