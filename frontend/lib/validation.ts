export interface RegisterValues {
  parentName: string;
  childName: string;
  grade: string;
  pin: string;
  confirmPin: string;
}

export type FieldErrors<K extends string> = Partial<Record<K, string>>;

const PIN_PATTERN = /^\d{4,6}$/;

export function validateRegister(values: RegisterValues): FieldErrors<keyof RegisterValues> {
  const errors: FieldErrors<keyof RegisterValues> = {};
  if (!values.parentName.trim()) errors.parentName = "Please enter your name.";
  if (!values.childName.trim()) errors.childName = "Please enter your child's name.";
  if (!values.grade) errors.grade = "Please select a grade.";
  if (!PIN_PATTERN.test(values.pin)) errors.pin = "Use 4 to 6 digits.";
  if (!values.confirmPin) errors.confirmPin = "Please confirm your PIN.";
  else if (values.confirmPin !== values.pin) errors.confirmPin = "The PINs don't match.";
  return errors;
}

export function validateLogin(userId: string, pin: string): FieldErrors<"userId" | "pin"> {
  const errors: FieldErrors<"userId" | "pin"> = {};
  if (!userId.trim()) errors.userId = "Please enter your User ID.";
  if (!PIN_PATTERN.test(pin)) errors.pin = "Enter your 4 to 6 digit PIN.";
  return errors;
}
