!macro NSIS_HOOK_PREINSTALL
  ; 重装时清理旧的 sidecar 目录，避免残留文件
  RMDir /r "$INSTDIR\build-sidecar\tauri-bridge"
!macroend
