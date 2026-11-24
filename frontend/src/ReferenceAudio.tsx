import { useState } from 'react'

export default function ReferenceAudio({ file, setFile, disabled }: {
  file: File | null
  setFile: (file: File | null) => void
  disabled: boolean
}) {
  const [error, setError] = useState('')

  function selectAudio(files: FileList) {
    if (disabled) return
    const audio = files[0]
    if (files.length !== 1 || !(audio.type.startsWith('audio/') ||
      (!audio.type && /\.(wav|mp3|m4a|ogg|flac|aac|opus)$/i.test(audio.name)))) {
      setFile(null)
      setError('Selecione um único arquivo de áudio.')
      return
    }
    setFile(audio)
    setError('')
  }

  return (
    <div>
      <label
        className="reference-drop"
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => {
          event.preventDefault()
          selectAudio(event.dataTransfer.files)
        }}
      >
        <strong>Áudio de referência</strong>
        <span>Arraste um arquivo de áudio ou clique para escolher uma gravação da voz que deseja usar na narração. Use pelo menos um segundo de fala; serão usados até dez segundos.</span>
        <input
          type="file"
          disabled={disabled}
          accept="audio/*,.wav,.mp3,.m4a,.ogg,.flac,.aac,.opus"
          onChange={(event) => {
            const files = event.target.files
            if (files?.length) selectAudio(files)
            event.target.value = ''
          }}
        />
      </label>
      {error && <p role="alert">{error}</p>}
      {file && <p role="status">Arquivo selecionado: {file.name}</p>}
    </div>
  )
}
