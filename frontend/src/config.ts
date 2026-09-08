const DEFAULT_PROJECT_ID = 'PRJ-ALTAI-R7-B'

export const projectId =
  import.meta.env.VITE_PROJECT_ID?.trim() || DEFAULT_PROJECT_ID
