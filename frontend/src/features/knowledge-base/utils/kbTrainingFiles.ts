const TRAINING_FILE_ACCEPT =
  ".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain";

export function isTrainingTextFile(file: File): boolean {
  const name = file.name.toLowerCase();
  return file.type === "text/plain" || name.endsWith(".txt");
}

export function isTrainingDocumentFile(file: File): boolean {
  const name = file.name.toLowerCase();
  return (
    name.endsWith(".pdf") ||
    name.endsWith(".docx") ||
    file.type === "application/pdf" ||
    file.type === "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
  );
}

export function isSupportedTrainingFile(file: File): boolean {
  return isTrainingTextFile(file) || isTrainingDocumentFile(file);
}

export function mergeTrainingFiles(existing: File[], incoming: File[]): File[] {
  const next = [...existing];
  for (const file of incoming) {
    if (!isSupportedTrainingFile(file)) continue;
    const duplicate = next.some(
      (item) => item.name === file.name && item.size === file.size && item.lastModified === file.lastModified
    );
    if (!duplicate) next.push(file);
  }
  return next;
}

export async function readTrainingTextFile(file: File): Promise<string> {
  return file.text();
}

// A backend `estimate_chars_from_size` képletével szinkronban: csak becslés —
// a pontos karakter-szám a backend feldolgozás során derül ki.
export function estimateCharsFromFile(file: File): number {
  const size = Math.max(0, Number(file.size ?? 0));
  if (size <= 0) return 0;
  const name = (file.name ?? "").toLowerCase();
  if (name.endsWith(".txt")) return size;
  if (name.endsWith(".pdf")) return Math.max(1, Math.round(size * 0.06));
  if (name.endsWith(".docx")) return Math.max(1, Math.round(size * 0.2));
  return Math.max(1, Math.round(size * 0.35));
}

export { TRAINING_FILE_ACCEPT };
