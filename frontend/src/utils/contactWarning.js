// Only the preferred method is shared with the other person on an errand, so
// warn when that choice would share nothing.
export function contactWarning({ contact_preference: preference, telegram_handle: telegram, phone_number: phone }) {
  if (!preference) {
    return "Choose a preferred contact method so the other person on your errand can reach you. Only that method is shared, and only after an errand is accepted.";
  }
  if (preference === "TELEGRAM" && !telegram?.trim()) {
    return "Add your Telegram handle, or choose another contact method.";
  }
  if (preference === "PHONE" && !phone?.trim()) {
    return "Add your phone number, or choose another contact method.";
  }
  return "";
}
