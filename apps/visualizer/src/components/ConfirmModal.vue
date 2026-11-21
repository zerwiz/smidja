<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { answerConfirm, confirmState } from '../lib/confirm'

const okBtn = ref<HTMLButtonElement | null>(null)

watch(
  () => confirmState.open,
  async (open) => {
    if (open) {
      await nextTick()
      okBtn.value?.focus()
    }
  },
)

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') answerConfirm(false)
  if (e.key === 'Enter') answerConfirm(true)
}
</script>

<template>
  <div v-if="confirmState.open && confirmState.req" class="cm-backdrop" @click.self="answerConfirm(false)" @keydown="onKey">
    <div class="cm-box" role="alertdialog" aria-modal="true" :aria-label="confirmState.req.title">
      <div class="cm-title">{{ confirmState.req.title }}</div>
      <div class="cm-msg">{{ confirmState.req.message }}</div>
      <div class="cm-actions">
        <button class="cm-btn" type="button" @click="answerConfirm(false)">{{ confirmState.req.cancelLabel }}</button>
        <button
          ref="okBtn"
          class="cm-btn cm-ok"
          :class="{ danger: confirmState.req.danger }"
          type="button"
          @click="answerConfirm(true)"
        >{{ confirmState.req.confirmLabel }}</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.cm-backdrop {
  position: fixed; inset: 0; z-index: 1000; display: flex; align-items: center; justify-content: center;
  background: rgba(0, 0, 0, 0.55); backdrop-filter: blur(2px);
}
.cm-box {
  min-width: 320px; max-width: 460px; padding: 18px 20px 14px; border-radius: 10px;
  background: var(--panel, #161616); color: var(--text, #eee); border: 1px solid var(--border, #333);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5);
}
.cm-title { font-size: 15px; font-weight: 600; margin-bottom: 8px; }
.cm-msg { font-size: 13px; color: var(--dim, #aaa); line-height: 1.5; white-space: pre-wrap; }
.cm-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
.cm-btn {
  padding: 6px 14px; border-radius: 6px; cursor: pointer; font: inherit; font-size: 13px;
  background: var(--panel-2, #1f1f1f); color: var(--text, #eee); border: 1px solid var(--border, #333);
}
.cm-btn:hover { border-color: var(--blue, #4a8cff); }
.cm-ok { border-color: var(--accent, #c9a227); }
.cm-ok.danger { background: var(--red, #b33); border-color: var(--red, #b33); color: #fff; }
.cm-btn:focus-visible { outline: 2px solid var(--blue, #4a8cff); outline-offset: 2px; }
</style>
