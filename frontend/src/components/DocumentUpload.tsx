import { useRef } from 'react';
import { Paperclip } from 'lucide-react';
import { toast } from 'sonner';
import { useQueryClient } from '@tanstack/react-query';
import { collectionsApi } from '../api/client';

interface Props {
  collectionId: string;
  disabled?: boolean;
}

const ACCEPTED = '.pdf,.docx,.txt';

export function DocumentUpload({ collectionId, disabled }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();

  async function handleFile(file: File) {
    const toastId = toast.loading(`Uploading ${file.name}…`);
    try {
      await collectionsApi.uploadDocument(collectionId, file);
      toast.success(`${file.name} uploaded`, { id: toastId });
      queryClient.invalidateQueries({ queryKey: ['collections'] });
    } catch {
      toast.error(`Failed to upload ${file.name}`, { id: toastId });
    }
  }

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED}
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFile(file);
          e.target.value = '';
        }}
      />
      <button
        type="button"
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
        className="p-2 text-gray-400 hover:text-white disabled:opacity-50 transition-colors"
        title="Upload document"
      >
        <Paperclip size={18} />
      </button>
    </>
  );
}
