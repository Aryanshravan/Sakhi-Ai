"use client";

import { useState, type FormEvent } from "react";
import { api, ApiError } from "@/lib/api";
import type { Profile, ReportLanguage } from "@/lib/types";
import { validateRegister, type FieldErrors, type RegisterValues } from "@/lib/validation";
import { GradeSelect } from "./GradeSelect";
import { LanguageSelector } from "./LanguageSelector";
import { PinField } from "./PinField";
import { FormError, SubmitButton } from "./SubmitButton";
import { TextField } from "./TextField";

const EMPTY: RegisterValues = { parentName: "", childName: "", grade: "", pin: "", confirmPin: "" };

export function RegisterForm({ onRegistered }: { onRegistered: (profile: Profile) => void }) {
  const [values, setValues] = useState(EMPTY);
  const [language, setLanguage] = useState<ReportLanguage>("en");
  const [errors, setErrors] = useState<FieldErrors<keyof RegisterValues>>({});
  const [formError, setFormError] = useState("");
  const [loading, setLoading] = useState(false);

  const set = (field: keyof RegisterValues) => (value: string) => {
    setValues((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined }));
  };

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const found = validateRegister(values);
    setErrors(found);
    setFormError("");
    if (Object.keys(found).length > 0) return;

    setLoading(true);
    try {
      const profile = await api<Profile>("/auth/register", {
        method: "POST",
        body: {
          parent_name: values.parentName.trim(),
          child_name: values.childName.trim(),
          grade: Number(values.grade),
          report_language: language,
          pin: values.pin,
        },
      });
      setValues(EMPTY);
      setLoading(false);
      onRegistered(profile);
    } catch (error) {
      setFormError(error instanceof ApiError ? error.message : "Something went wrong. Please try again.");
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-5">
      <TextField
        id="parent-name"
        label="Parent's Name"
        placeholder="Enter your name"
        autoComplete="name"
        maxLength={60}
        value={values.parentName}
        onChange={(event) => set("parentName")(event.target.value)}
        error={errors.parentName}
        disabled={loading}
      />
      <TextField
        id="child-name"
        label="Child's Name"
        placeholder="Enter your child's name"
        autoComplete="off"
        maxLength={60}
        value={values.childName}
        onChange={(event) => set("childName")(event.target.value)}
        error={errors.childName}
        disabled={loading}
      />
      <GradeSelect value={values.grade} onChange={set("grade")} error={errors.grade} disabled={loading} />
      <LanguageSelector value={language} onChange={setLanguage} disabled={loading} />
      <div className="grid gap-5 sm:grid-cols-2">
        <PinField
          id="pin"
          label="Create PIN"
          hint="4 to 6 digits"
          autoComplete="new-password"
          value={values.pin}
          onChange={set("pin")}
          error={errors.pin}
          disabled={loading}
        />
        <PinField
          id="confirm-pin"
          label="Confirm PIN"
          autoComplete="new-password"
          value={values.confirmPin}
          onChange={set("confirmPin")}
          error={errors.confirmPin}
          disabled={loading}
        />
      </div>
      {formError && <FormError message={formError} />}
      <SubmitButton label="Let's Get Started" loadingLabel="Creating your profile…" loading={loading} />
    </form>
  );
}
