let _id = 0

export const toast = (message, type = 'info') => {
  window.dispatchEvent(new CustomEvent('app:toast', {
    detail: { message, type, id: ++_id },
  }))
}
