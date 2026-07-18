import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import {
  parseTrainingQuotaError,
  type TrainingQuotaErrorDetail,
} from "../../../api/services/kb/kbIngestApi";
import { useBillingOverview } from "../../billing/hooks/useBilling";
import { queryKeys } from "../../../queryKeys";
import { getApiErrorMessage, isDuplicateContentError } from "../../../utils/getApiErrorMessage";
import type { KbItem } from "./useKb";
import { useCreateFileIngestMutation, useCreateTextIngestMutation, useIngestRun } from "./useKb";
import {
  getTrainingFailureMessage,
  getTrainingProgress,
  getTrainingRunRefetchInterval,
  getTrainingStatusDetail,
  isTrainingActive,
} from "../utils/trainingProgress";
import {
  estimateCharsFromFile,
  isSupportedTrainingFile,
  mergeTrainingFiles,
  readTrainingTextFile,
} from "../utils/kbTrainingFiles";

type UseKbTrainingSessionOptions = {
  billingRestricted?: boolean;
  t: (key: string) => string;
  onTrainingComplete?: (kbUuid: string) => void;
};

export function useKbTrainingSession({ billingRestricted = false, t, onTrainingComplete }: UseKbTrainingSessionOptions) {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [trainingKb, setTrainingKb] = useState<KbItem | null>(null);
  const [showTrainModal, setShowTrainModal] = useState(false);
  const [textValue, setTextValue] = useState("");
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [showProgressModal, setShowProgressModal] = useState(false);
  const [activeTrainingRunId, setActiveTrainingRunId] = useState<string | undefined>();
  const [quotaError, setQuotaError] = useState<TrainingQuotaErrorDetail | null>(null);
  const pendingTextAfterFilesRef = useRef<string | null>(null);

  const createTextMutation = useCreateTextIngestMutation();
  const createFileMutation = useCreateFileIngestMutation();
  const activeTrainingRunQuery = useIngestRun(activeTrainingRunId, {
    refetchInterval: ({ state }) => getTrainingRunRefetchInterval(state.data?.status),
  });
  const activeTrainingRun = activeTrainingRunQuery.data;
  const trainingProgress = useMemo(() => getTrainingProgress(activeTrainingRun), [activeTrainingRun]);
  const trainingStatusDetail = useMemo(() => getTrainingStatusDetail(activeTrainingRun, t), [activeTrainingRun, t]);
  const submitting = createTextMutation.isPending || createFileMutation.isPending;
  const loading = submitting || isTrainingActive(activeTrainingRun?.status);

  // Tanítási kvóta — a billing overview-ból olvassuk a maradék karaktert, hogy
  // a modal-ban a "Tanításra felhasználható karakterek száma" sor megjelenjen.
  const billingOverviewQuery = useBillingOverview();
  const remainingTrainingChars = useMemo<number | null>(() => {
    const training = (billingOverviewQuery.data?.usage?.training ?? null) as
      | Record<string, unknown>
      | null;
    if (!training) return null;
    const raw =
      training.remaining_training_chars ??
      training.remaining_chars ??
      null;
    if (typeof raw !== "number" || Number.isNaN(raw)) return null;
    return Math.max(0, raw);
  }, [billingOverviewQuery.data]);

  const pendingTrainingChars = useMemo<number>(() => {
    if (selectedFiles.length > 0) {
      return selectedFiles.reduce((sum, file) => sum + estimateCharsFromFile(file), 0);
    }
    return textValue.length;
  }, [selectedFiles, textValue]);

  const resetForm = useCallback(() => {
    setTextValue("");
    setSelectedFiles([]);
    setDragOver(false);
    pendingTextAfterFilesRef.current = null;
    if (fileInputRef.current) fileInputRef.current.value = "";
  }, []);

  const handleTrainingQuotaError = useCallback(
    (error: unknown): boolean => {
      const quota = parseTrainingQuotaError(error);
      if (!quota) return false;
      // A tanítási modal-ba inline jelenítjük meg a kvóta hibát, hogy a
      // felhasználó láthassa a részleteket és a "Csomag bővítése" linket.
      setQuotaError(quota);
      return true;
    },
    []
  );

  const clearQuotaError = useCallback(() => {
    setQuotaError(null);
  }, []);

  const closeTrainModal = useCallback(() => {
    if (loading) return;
    setShowTrainModal(false);
    setTrainingKb(null);
    setQuotaError(null);
    resetForm();
  }, [loading, resetForm]);

  const openTraining = useCallback(
    (kb: KbItem) => {
      if (billingRestricted || kb.can_train !== true) return;
      resetForm();
      setQuotaError(null);
      setTrainingKb(kb);
      setShowTrainModal(true);
    },
    [billingRestricted, resetForm]
  );

  const startTextTraining = useCallback(
    (kbUuid: string, text: string) => {
      createTextMutation.mutate(
        { kbUuid, text },
        {
          onSuccess: (run) => {
            setActiveTrainingRunId(run.id);
            setShowProgressModal(true);
            setShowTrainModal(false);
            resetForm();
            void queryClient.invalidateQueries({ queryKey: queryKeys.kbIngestRuns(kbUuid) });
          },
          onError: (error) => {
            if (handleTrainingQuotaError(error)) return;
            if (isDuplicateContentError(error)) {
              toast.info(`${t("chat.trainingAborted")} ${getApiErrorMessage(error) ?? t("kb.errorDuplicateContent")}`);
              return;
            }
            toast.error(getApiErrorMessage(error) ?? t("chat.textTrainingStartError"));
          },
        }
      );
    },
    [createTextMutation, handleTrainingQuotaError, queryClient, resetForm, t]
  );

  const startFileTraining = useCallback(
    (kbUuid: string, files: File[]) => {
      createFileMutation.mutate(
        { kbUuid, files },
        {
          onSuccess: (run) => {
            setActiveTrainingRunId(run.id);
            setShowProgressModal(true);
            setShowTrainModal(false);
            resetForm();
            void queryClient.invalidateQueries({ queryKey: queryKeys.kbIngestRuns(kbUuid) });
          },
          onError: (error) => {
            pendingTextAfterFilesRef.current = null;
            if (handleTrainingQuotaError(error)) return;
            if (isDuplicateContentError(error)) {
              toast.info(`${t("chat.trainingAborted")} ${getApiErrorMessage(error) ?? t("kb.errorDuplicateContent")}`);
              return;
            }
            toast.error(getApiErrorMessage(error) ?? t("chat.fileTrainingStartError"));
          },
        }
      );
    },
    [createFileMutation, handleTrainingQuotaError, queryClient, resetForm, startTextTraining, t]
  );

  const submitTraining = useCallback(() => {
    if (!trainingKb?.uuid || loading) return;
    const text = textValue.trim();
    const files = selectedFiles;
    if (!text && files.length === 0) return;

    setQuotaError(null);

    if (files.length > 0) {
      if (text) pendingTextAfterFilesRef.current = textValue;
      startFileTraining(trainingKb.uuid, files);
      return;
    }
    startTextTraining(trainingKb.uuid, textValue);
  }, [loading, selectedFiles, startFileTraining, startTextTraining, textValue, trainingKb?.uuid]);

  const addFiles = useCallback(async (files: FileList | File[] | null | undefined) => {
    if (!files?.length) return;
    const supported = Array.from(files).filter(isSupportedTrainingFile);
    if (!supported.length) {
      toast.error(t("kb.trainUnsupportedFile"));
      return;
    }
    const textFiles = supported.filter((file) => file.name.toLowerCase().endsWith(".txt") || file.type === "text/plain");
    const documentFiles = supported.filter((file) => !textFiles.includes(file));

    if (textFiles.length) {
      const chunks = await Promise.all(textFiles.map((file) => readTrainingTextFile(file)));
      const merged = chunks.filter(Boolean).join("\n\n").trim();
      if (merged) {
        setTextValue((current) => (current.trim() ? `${current.trim()}\n\n${merged}` : merged));
      }
    }
    if (documentFiles.length) {
      setSelectedFiles((current) => mergeTrainingFiles(current, documentFiles));
    }
  }, [t]);

  const removeFile = useCallback((index: number) => {
    setSelectedFiles((current) => current.filter((_, itemIndex) => itemIndex !== index));
  }, []);

  useEffect(() => {
    if (!activeTrainingRunId || !activeTrainingRun) return;
    if (isTrainingActive(activeTrainingRun.status)) {
      setShowProgressModal(true);
      return;
    }
    setShowProgressModal(false);
    const kbUuid = trainingKb?.uuid;
    const queuedText = pendingTextAfterFilesRef.current?.trim();
    if (
      queuedText &&
      kbUuid &&
      (activeTrainingRun.status === "completed" || activeTrainingRun.status === "partial_success")
    ) {
      pendingTextAfterFilesRef.current = null;
      startTextTraining(kbUuid, queuedText);
      setActiveTrainingRunId(undefined);
      return;
    }
    pendingTextAfterFilesRef.current = null;
    if (activeTrainingRun.status === "completed" || activeTrainingRun.status === "partial_success") {
      toast.success(t("kb.trainingStartedNotice"));
      void queryClient.invalidateQueries({ queryKey: queryKeys.kb });
      if (kbUuid) onTrainingComplete?.(kbUuid);
    } else {
      toast.error(getTrainingFailureMessage(activeTrainingRun, t) ?? t("chat.trainingFailed"));
    }
    setActiveTrainingRunId(undefined);
    setTrainingKb(null);
  }, [
    activeTrainingRun,
    activeTrainingRunId,
    onTrainingComplete,
    queryClient,
    startTextTraining,
    t,
    trainingKb?.uuid,
  ]);

  const canSubmit = Boolean(textValue.trim() || selectedFiles.length) && !loading;

  return {
    fileInputRef,
    trainingKb,
    showTrainModal,
    showProgressModal,
    textValue,
    setTextValue,
    selectedFiles,
    dragOver,
    setDragOver,
    loading,
    submitting,
    canSubmit,
    trainingProgress,
    trainingStatusDetail,
    quotaError,
    remainingTrainingChars,
    pendingTrainingChars,
    openTraining,
    closeTrainModal,
    clearQuotaError,
    submitTraining,
    addFiles,
    removeFile,
  };
}
