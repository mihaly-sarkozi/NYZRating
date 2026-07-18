import type { DragEvent } from "react";

import { useKbTrainingSession } from "../../hooks/useKbTrainingSession";
import KbTrainingModal from "./KbTrainingModal";
import KbTrainingProgressModal from "./KbTrainingProgressModal";

type KbTrainingDialogsProps = {
  t: (key: string) => string;
  session: ReturnType<typeof useKbTrainingSession>;
};

export function KbTrainingDialogs({ t, session }: KbTrainingDialogsProps) {
  const onDragOver = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    session.setDragOver(true);
  };
  const onDragLeave = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    session.setDragOver(false);
  };
  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    session.setDragOver(false);
    void session.addFiles(event.dataTransfer?.files);
  };

  return (
    <>
      <KbTrainingModal
        open={session.showTrainModal}
        kbName={session.trainingKb?.name ?? t("kb.title")}
        textValue={session.textValue}
        selectedFiles={session.selectedFiles}
        dragOver={session.dragOver}
        loading={session.loading}
        canSubmit={session.canSubmit}
        fileInputRef={session.fileInputRef}
        quotaError={session.quotaError}
        onClearQuotaError={session.clearQuotaError}
        remainingTrainingChars={session.remainingTrainingChars}
        t={t}
        onClose={session.closeTrainModal}
        onSubmit={session.submitTraining}
        onTextChange={session.setTextValue}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        onSelectFiles={(files) => void session.addFiles(files)}
        onRemoveFile={session.removeFile}
      />
      <KbTrainingProgressModal
        open={session.showProgressModal}
        progress={session.trainingProgress}
        statusDetail={session.trainingStatusDetail}
        t={t}
      />
    </>
  );
}
