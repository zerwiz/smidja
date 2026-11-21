/**
 * The app's own confirm dialog — never the browser's `confirm()`, whose box names the
 * host ("localhost says …") and cannot be styled. One dialog for the whole app, mounted
 * once in App.vue (ConfirmModal.vue); any view awaits `askConfirm(...)`.
 */
import { reactive } from 'vue'

export interface ConfirmRequest {
  title: string
  message: string
  confirmLabel: string
  cancelLabel: string
  danger: boolean
}

export const confirmState = reactive<{ open: boolean; req: ConfirmRequest | null }>({ open: false, req: null })

let settle: ((ok: boolean) => void) | null = null

export function askConfirm(opts: Partial<ConfirmRequest> & { message: string }): Promise<boolean> {
  settle?.(false)                       // a second ask answers the first with "no"
  confirmState.req = {
    title: opts.title ?? 'Are you sure?',
    message: opts.message,
    confirmLabel: opts.confirmLabel ?? 'Confirm',
    cancelLabel: opts.cancelLabel ?? 'Cancel',
    danger: opts.danger ?? false,
  }
  confirmState.open = true
  return new Promise<boolean>((resolve) => {
    settle = resolve
  })
}

export function answerConfirm(ok: boolean): void {
  confirmState.open = false
  const s = settle
  settle = null
  s?.(ok)
}
