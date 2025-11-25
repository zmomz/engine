import { create } from 'zustand';

interface ConfirmOptions {
  title?: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
}

interface ConfirmState {
  isOpen: boolean;
  options: ConfirmOptions;
  resolve: ((value: boolean) => void) | null;
  requestConfirm: (options: ConfirmOptions) => Promise<boolean>;
  closeConfirm: (result: boolean) => void;
}

const useConfirmStore = create<ConfirmState>((set, get) => ({
  isOpen: false,
  options: { message: '' },
  resolve: null,
  requestConfirm: (options) => {
    return new Promise((resolve) => {
      set({ isOpen: true, options, resolve });
    });
  },
  closeConfirm: (result) => {
    const { resolve } = get();
    if (resolve) {
      resolve(result);
    }
    set({ isOpen: false, resolve: null });
  },
}));

export default useConfirmStore;
